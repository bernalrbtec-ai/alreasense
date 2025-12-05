"""
Views para o módulo Flow Chat.
Integra com permissões multi-tenant e departamentos.
"""
import logging
import os
import asyncio
import threading
import httpx
from datetime import datetime
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import time

from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction
from apps.chat.api.serializers import (
    ConversationSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    MessageAttachmentSerializer,
    MessageReactionSerializer
)
from apps.authn.permissions import CanAccessChat
from apps.authn.mixins import DepartmentFilterMixin
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection
from apps.chat.utils.metrics import get_metrics, get_worker_status, record_latency, record_error
from apps.chat.redis_queue import get_queue_metrics


REFRESH_INFO_MIN_INTERVAL_SECONDS = 900  # 15 minutos entre refresh completo
REFRESH_INFO_CACHE_SECONDS = 300  # 5 minutos no cache curto

logger = logging.getLogger(__name__)

# Função auxiliar para detectar se um número é LID (não é telefone válido)
def is_lid_number(phone: str) -> bool:
    """
    Detecta se um número é LID (Local ID do WhatsApp) ao invés de telefone real.
    LIDs sempre terminam com @lid. Números com @g.us são grupos válidos, não LIDs.
    """
    if not phone:
        return False
    
    # ✅ CORREÇÃO CRÍTICA: Verificar sufixo primeiro
    # @g.us = grupo válido (NÃO é LID)
    # @lid = LID de usuário (É LID)
    # @s.whatsapp.net = JID de usuário (NÃO é LID)
    if phone.endswith('@lid'):
        return True
    if phone.endswith('@g.us') or phone.endswith('@s.whatsapp.net'):
        return False
    
    # Se não tem sufixo, verificar se número é muito longo (provavelmente LID)
    clean = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').strip()
    
    # Se tem 16+ dígitos sem sufixo, provavelmente é LID
    if len(clean) >= 16:
        return True
    
    return False

def fetch_pushname_from_evolution(instance: WhatsAppInstance, phone: str) -> str | None:
    """
    Busca pushname de um contato via Evolution API.
    
    Args:
        instance: Instância WhatsApp ativa
        phone: Telefone em formato E.164 (ex: +5517996196795) ou sem formatação
    
    Returns:
        Pushname do contato ou None se não encontrado
    """
    try:
        from apps.notifications.services import normalize_phone
        from django.conf import settings
        
        # Normalizar telefone (remover + e @s.whatsapp.net)
        clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '').strip()
        
        # Buscar configuração da Evolution API
        base_url = getattr(settings, 'EVOLUTION_API_URL', None)
        api_key = getattr(settings, 'EVOLUTION_API_KEY', None)
        
        if not base_url or not api_key:
            logger.warning("⚠️ [PUSHNAME] Evolution API não configurada")
            return None
        
        # Endpoint da Evolution API para buscar informações de contato
        base_url_clean = base_url.rstrip('/')
        endpoint = f"{base_url_clean}/chat/whatsappNumbers/{instance.instance_name}"
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        # Fazer requisição POST com lista de números
        response = httpx.post(
            endpoint,
            json={'numbers': [clean_phone]},
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                contact_info = data[0]
                # Retornar pushname ou name (prioridade: pushname > name)
                pushname = contact_info.get('pushname') or contact_info.get('name', '')
                if pushname and not is_lid_number(pushname):
                    logger.info(f"   ✅ [PUSHNAME] Encontrado via Evolution API: {pushname} para {phone}")
                    return pushname
        
        logger.debug(f"   ℹ️ [PUSHNAME] Pushname não encontrado para {phone}")
        return None
        
    except httpx.TimeoutException:
        logger.warning(f"   ⚠️ [PUSHNAME] Timeout ao buscar pushname para {phone}")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"   ⚠️ [PUSHNAME] Erro HTTP ao buscar pushname para {phone}: {e}")
        return None
    except Exception as e:
        logger.warning(f"   ⚠️ [PUSHNAME] Erro ao buscar pushname para {phone}: {e}")
        return None

def clean_participants_for_metadata(participants_list: list) -> list:
    """
    Limpa lista de participantes garantindo que phone sempre tenha telefone real.
    Se phone é LID ou vazio, tenta usar phoneNumber para obter telefone real.
    
    Args:
        participants_list: Lista de participantes com phone, jid, name, phoneNumber, etc.
    
    Returns:
        Lista limpa de participantes (phone sempre com telefone real, nunca LID)
    """
    cleaned = []
    from apps.notifications.services import normalize_phone
    
    for p in participants_list:
        participant_phone = p.get('phone', '')
        participant_jid = p.get('jid', '')
        participant_phone_number = p.get('phoneNumber', '') or p.get('phone_number', '')
        
        # Criar cópia do participante
        cleaned_p = p.copy()
        
        # ✅ CORREÇÃO CRÍTICA: Se phone é LID ou vazio, tentar usar phoneNumber
        if not participant_phone or is_lid_number(participant_phone):
            if participant_phone_number:
                # Extrair telefone do phoneNumber (JID real @s.whatsapp.net)
                phone_raw = participant_phone_number.split('@')[0]
                normalized_phone = normalize_phone(phone_raw)
                if normalized_phone:
                    cleaned_p['phone'] = normalized_phone
                    logger.info(f"   ✅ [CLEAN PARTICIPANTS] Usando phoneNumber para preencher phone: {participant_jid} -> {normalized_phone}")
                else:
                    # Se não conseguiu normalizar, remover phone
                    cleaned_p['phone'] = ''
                    logger.warning(f"   ⚠️ [CLEAN PARTICIPANTS] Não conseguiu normalizar phoneNumber: {participant_phone_number}")
            else:
                # Se não tem phoneNumber, remover phone (não salvar LID)
                cleaned_p['phone'] = ''
                logger.warning(f"   ⚠️ [CLEAN PARTICIPANTS] Participante sem phoneNumber válido: {participant_jid}")
        elif participant_jid and participant_jid.endswith('@lid'):
            # Se JID é @lid, garantir que phone não é LID
            if participant_phone and is_lid_number(participant_phone):
                # Tentar usar phoneNumber se disponível
                if participant_phone_number:
                    phone_raw = participant_phone_number.split('@')[0]
                    normalized_phone = normalize_phone(phone_raw)
                    if normalized_phone:
                        cleaned_p['phone'] = normalized_phone
                        logger.info(f"   ✅ [CLEAN PARTICIPANTS] JID @lid: usando phoneNumber: {normalized_phone}")
                    else:
                        cleaned_p['phone'] = ''
                else:
                    cleaned_p['phone'] = ''
                    logger.warning(f"   ⚠️ [CLEAN PARTICIPANTS] JID @lid sem phoneNumber: {participant_jid}")
        
        # ✅ VALIDAÇÃO CRÍTICA: Garantir que name não seja LID
        participant_name = cleaned_p.get('name', '')
        if participant_name and is_lid_number(participant_name):
            logger.warning(f"   ⚠️ [CLEAN PARTICIPANTS] name é LID, removendo: {participant_name[:30]}...")
            cleaned_p['name'] = ''  # Não usar LID como nome
        
        # ✅ VALIDAÇÃO CRÍTICA: Garantir que pushname não seja LID
        participant_pushname = cleaned_p.get('pushname', '')
        if participant_pushname and is_lid_number(participant_pushname):
            logger.warning(f"   ⚠️ [CLEAN PARTICIPANTS] pushname é LID, removendo: {participant_pushname[:30]}...")
            cleaned_p['pushname'] = ''  # Não usar LID como pushname
        
        cleaned.append(cleaned_p)
    
    return cleaned

class ConversationViewSet(DepartmentFilterMixin, viewsets.ModelViewSet):
    """
    ViewSet para conversas.
    
    Filtros automáticos por tenant e departamento conforme permissões do usuário:
    - Admin: vê todas do tenant
    - Gerente/Agente: vê apenas dos seus departamentos
    """
    
    queryset = Conversation.objects.select_related(
        'tenant', 'department', 'assigned_to'
    ).prefetch_related('participants')
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'department', 'assigned_to']
    search_fields = ['contact_phone', 'contact_name']
    ordering_fields = ['last_message_at', 'created_at']
    # ✅ FIX: Removido ordering padrão - será aplicado no get_queryset com tratamento de NULL
    # ordering = ['-last_message_at']  # Removido para evitar erro com NULL
    
    def get_permissions(self):
        """
        Permite acesso público ao endpoint profile-pic-proxy.
        Todos os outros endpoints requerem autenticação.
        """
        if self.action == 'profile_pic_proxy':
            return [AllowAny()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        """Usa serializer detalhado no retrieve."""
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        """
        Override para incluir conversas pending (Inbox) no filtro.
        Admin: vê tudo do tenant (incluindo pending)
        Gerente/Agente: vê apenas dos seus departamentos + pending do tenant
        
        REGRA IMPORTANTE: Conversas com departamento NÃO aparecem no Inbox,
        mesmo que tenham status='pending'
        
        ✅ PERFORMANCE: Otimizações aplicadas:
        - Calcula unread_count em batch (evita N+1 queries)
        - Prefetch última mensagem (evita N+1 queries)
        
        ✅ SEGURANÇA CRÍTICA: SEMPRE filtrar por tenant para evitar vazamento de dados
        """
        from django.db.models import Prefetch, Count, Q, OuterRef, Subquery
        from apps.chat.models import Message
        
        queryset = super().get_queryset()
        user = self.request.user
        
        # ✅ SEGURANÇA CRÍTICA: SEMPRE filtrar por tenant primeiro
        # Isso previne vazamento de dados entre tenants
        # EXCEÇÃO: Superusers podem precisar acessar múltiplos tenants (para debug/admin)
        # Mas por padrão, mesmo superusers devem ter tenant associado
        if not user.is_authenticated:
            return queryset.none()
        
        # Se não tem tenant, retornar vazio (mesmo para superuser)
        # Superusers devem ter tenant associado para operações normais
        if not user.tenant:
            logger.warning(
                f"⚠️ [SEGURANÇA] Usuário {user.email} sem tenant associado. "
                f"Bloqueando acesso a conversas."
            )
            return queryset.none()
        
        # Filtrar por tenant (aplicado para TODOS os usuários, incluindo superusers)
        queryset = queryset.filter(tenant=user.tenant)
        
        # ✅ PERFORMANCE: Calcular unread_count em batch usando annotate
        # Isso evita N+1 queries quando serializer acessa unread_count
        queryset = queryset.annotate(
            unread_count_annotated=Count(
                'messages',
                filter=Q(
                    messages__direction='incoming',
                    messages__status__in=['sent', 'delivered']
                ),
                distinct=True
            )
        )
        
        # ✅ PERFORMANCE: Prefetch última mensagem para evitar N+1 queries
        # Usa Prefetch com queryset customizado para buscar apenas última mensagem
        last_message_queryset = Message.objects.select_related(
            'sender', 'conversation'
        ).prefetch_related('attachments').order_by('-created_at')
        
        queryset = queryset.prefetch_related(
            Prefetch(
                'messages',
                queryset=last_message_queryset[:1],  # Apenas última mensagem
                to_attr='last_message_list'
            )
        )
        
        # ✅ FIX: Tratar valores NULL em last_message_at na ordenação
        # PostgreSQL pode ter problemas ao ordenar por campos NULL quando há valores None
        # Usar Coalesce para substituir NULL por created_at
        from django.db.models.functions import Coalesce
        
        # Sempre aplicar tratamento de NULL para last_message_at
        queryset = queryset.annotate(
            last_message_at_safe=Coalesce('last_message_at', 'created_at')
        )
        
        # Verificar se há ordenação customizada do usuário
        ordering_param = self.request.query_params.get('ordering', '-last_message_at')
        
        # Se ordena por last_message_at (com ou sem -), usar a versão segura
        if 'last_message_at' in ordering_param:
            if ordering_param.startswith('-'):
                queryset = queryset.order_by('-last_message_at_safe', '-created_at')
            else:
                queryset = queryset.order_by('last_message_at_safe', '-created_at')
        else:
            # Se não ordena por last_message_at, usar ordenação padrão
            queryset = queryset.order_by('-last_message_at_safe', '-created_at')
        
        # 🔍 Verificar se está filtrando por status=pending (Inbox)
        status_filter = self.request.query_params.get('status')
        
        # Se filtrando por pending (Inbox), garantir que NÃO tenha departamento
        if status_filter == 'pending':
            queryset = queryset.filter(
                status='pending',
                department__isnull=True  # ← CRÍTICO: Apenas conversas SEM departamento no Inbox
            )
        
        # Admin vê tudo (incluindo pending)
        if user.is_admin:
            return queryset
        
        # Gerente e Agente vêem:
        # 1. Conversas dos seus departamentos
        # 2. Conversas pending (sem departamento) do tenant
        if user.is_gerente or user.is_agente:
            department_ids = user.departments.values_list('id', flat=True)
            
            return queryset.filter(
                Q(department__in=department_ids) |  # Suas conversas
                Q(department__isnull=True, status='pending')  # Inbox do tenant
            )
        
        return queryset.none()
    
    def perform_create(self, serializer):
        """Associa conversa ao tenant do usuário."""
        serializer.save(
            tenant=self.request.user.tenant,
            assigned_to=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def claim(self, request, pk=None):
        """
        Pega (claim) uma conversa pendente do Inbox e atribui a um departamento/agente.
        Body: {
            "department": "uuid",  # obrigatório
            "assigned_to": "user_id" (opcional, se não informado usa o usuário atual)
        }
        """
        conversation = self.get_object()
        
        # Verificar se está pendente
        if conversation.status != 'pending':
            return Response(
                {'error': 'Conversa não está pendente'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        department_id = request.data.get('department')
        assigned_to_id = request.data.get('assigned_to')
        
        if not department_id:
            return Response(
                {'error': 'department é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar departamento
        from apps.authn.models import Department, User
        try:
            department = Department.objects.get(
                id=department_id,
                tenant=request.user.tenant
            )
        except Department.DoesNotExist:
            return Response(
                {'error': 'Departamento não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar usuário atribuído (se fornecido)
        assigned_to = request.user  # Padrão: quem está pegando
        if assigned_to_id:
            try:
                assigned_to = User.objects.get(
                    id=assigned_to_id,
                    tenant=request.user.tenant
                )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Usuário não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Atualizar conversa
        conversation.department = department
        conversation.assigned_to = assigned_to
        conversation.status = 'open'
        conversation.save(update_fields=['department', 'assigned_to', 'status'])
        
        serializer = self.get_serializer(conversation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='refresh-info')
    def refresh_info(self, request, pk=None):
        """
        Atualiza informações da conversa (nome, foto, metadados) sob demanda.
        
        Funciona para GRUPOS e CONTATOS INDIVIDUAIS.
        Usado quando o usuário ABRE uma conversa.
        Cache Redis de 5min para evitar requisições repetidas.
        
        Returns:
            - 200: Informações atualizadas
            - 404: Instância Evolution não encontrada
            - 500: Erro ao buscar da API
        """
        import logging
        import httpx
        from django.core.cache import cache
        from apps.connections.models import EvolutionConnection
        
        logger = logging.getLogger(__name__)
        conversation = self.get_object()
        metadata = conversation.metadata or {}
        
        # Cooldown adicional baseado na última atualização persistida
        last_refresh_str = metadata.get('last_refresh_at')
        if last_refresh_str:
            last_refresh_dt = parse_datetime(last_refresh_str)
            if last_refresh_dt:
                if timezone.is_naive(last_refresh_dt):
                    last_refresh_dt = timezone.make_aware(last_refresh_dt, timezone.utc)
                elapsed = (timezone.now() - last_refresh_dt).total_seconds()
                if elapsed < REFRESH_INFO_MIN_INTERVAL_SECONDS:
                    remaining = int(REFRESH_INFO_MIN_INTERVAL_SECONDS - elapsed)
                    logger.info(
                        "⏳ [REFRESH] Conversa %s atualizada há %.1fs - usando dados existentes",
                        conversation.id,
                        elapsed
                    )
                    cache.set(f"conversation_info_{conversation.id}", True, REFRESH_INFO_CACHE_SECONDS)
                    return Response({
                        'message': 'Informações atualizadas recentemente',
                        'conversation': ConversationSerializer(conversation).data,
                        'from_cache': True,
                        'cooldown_seconds': max(0, remaining)
                    })
        
        # ✅ NOVO: Verificação ultra-refinada para grupos (antes de verificar cache)
        # Verifica se participantes precisam ser atualizados mesmo com cache válido
        needs_participants_refresh = False
        if conversation.conversation_type == 'group':
            group_metadata = conversation.group_metadata or {}
            participants = group_metadata.get('participants', [])
            participants_count = group_metadata.get('participants_count', 0)
            participants_updated_at = group_metadata.get('participants_updated_at')
            
            # ✅ Verificação 1: Timestamp de atualização (participantes > 1 hora = desatualizados)
            participants_stale = False
            if participants_updated_at:
                try:
                    from dateutil.parser import parse as parse_dt
                    updated_dt = parse_dt(participants_updated_at)
                    if timezone.is_naive(updated_dt):
                        updated_dt = timezone.make_aware(updated_dt, timezone.utc)
                    elapsed_hours = (timezone.now() - updated_dt).total_seconds() / 3600
                    if elapsed_hours > 1.0:  # Mais de 1 hora = desatualizado
                        participants_stale = True
                        logger.info(f"🔄 [REFRESH] Participantes desatualizados ({elapsed_hours:.1f}h atrás)")
                except Exception as e:
                    logger.warning(f"⚠️ [REFRESH] Erro ao verificar timestamp: {e}")
            
            # ✅ Verificação 2: Inconsistência (participants_count > 0 mas participants vazio)
            has_inconsistency = participants_count > 0 and len(participants) == 0
            if has_inconsistency:
                logger.info(f"🔄 [REFRESH] Inconsistência: participants_count={participants_count} mas participants vazio")
            
            # ✅ Verificação 3: Qualidade dos dados (menos de 50% válidos)
            has_poor_quality = False
            if len(participants) > 0:
                valid_count = sum(1 for p in participants 
                                 if p.get('phone') and not is_lid_number(p.get('phone', '')))
                # Se menos de 50% são válidos, considerar qualidade ruim
                if valid_count < len(participants) * 0.5:
                    has_poor_quality = True
                    logger.info(f"🔄 [REFRESH] Qualidade ruim: {valid_count}/{len(participants)} válidos")
            
            # ✅ Decisão: Ignorar cache apenas se realmente necessário
            needs_participants_refresh = (
                has_inconsistency or 
                has_poor_quality or 
                (participants_stale and len(participants) == 0)
            )
            
            if needs_participants_refresh:
                logger.info(f"🔄 [REFRESH] Ignorando cache Redis para atualizar participantes")
            else:
                logger.debug(f"✅ [REFRESH] Participantes OK, respeitando cache normalmente")
        
        # Verificar cache (5min) - mas ignorar se precisa atualizar participantes
        cache_key = f"conversation_info_{conversation.id}"
        if not needs_participants_refresh:
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"✅ [REFRESH] Cache hit para {conversation.id}")
                return Response({
                    'message': 'Informações em cache (atualizadas recentemente)',
                    'conversation': ConversationSerializer(conversation).data,
                    'from_cache': True
                })
        
        # Buscar instância WhatsApp ativa (NÃO Evolution Connection)
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ [REFRESH] Nenhuma instância WhatsApp ativa para tenant {request.user.tenant.name}")
            return Response(
                {'error': 'Nenhuma instância WhatsApp ativa encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Buscar configuração do servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            logger.error(f"❌ [REFRESH] Nenhum servidor Evolution configurado!")
            return Response(
                {'error': 'Servidor Evolution não configurado'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Buscar informações na Evolution API
        try:
            # Usar Evolution Server config + WhatsApp Instance name (UUID)
            base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
            api_key = wa_instance.api_key or evolution_server.api_key
            instance_name = wa_instance.instance_name  # UUID da instância
            
            headers = {
                'apikey': api_key,
                'Content-Type': 'application/json'
            }
            update_fields = []
            
            # 👥 GRUPOS: Endpoint /group/findGroupInfos
            if conversation.conversation_type == 'group':
                # ✅ CORREÇÃO CRÍTICA: Buscar JID correto usando fetchAllGroups
                # O contact_phone pode estar incorreto (ex: 55120363404279692186@g.us)
                # Mas o JID real é diferente (ex: 120363404279692186@g.us)
                raw_phone = conversation.contact_phone
                group_jid = None
                
                # ✅ NOVO: Tentar buscar JID correto usando fetchAllGroups
                try:
                    fetch_all_endpoint = f"{base_url}/group/fetchAllGroups/{instance_name}"
                    logger.info(f"🔍 [REFRESH GRUPO] Buscando JID correto via fetchAllGroups...")
                    
                    with httpx.Client(timeout=10.0) as client:
                        fetch_response = client.get(
                            fetch_all_endpoint,
                            params={'getParticipants': 'false'},
                            headers=headers
                        )
                        
                        if fetch_response.status_code == 200:
                            all_groups = fetch_response.json()
                            if isinstance(all_groups, list):
                                # Buscar grupo pelo nome (contact_name) ou tentar encontrar correspondente
                                group_name = conversation.contact_name or ''
                                for group in all_groups:
                                    group_id_from_api = group.get('id', '')
                                    group_subject = group.get('subject', '')
                                    
                                    # Se encontrou grupo com mesmo nome ou JID similar
                                    if group_id_from_api.endswith('@g.us'):
                                        # Se o nome corresponde ou se é o único grupo com tamanho similar
                                        if group_subject == group_name or (not group_name and group.get('size', 0) == conversation.group_metadata.get('size', 0) if conversation.group_metadata else False):
                                            group_jid = group_id_from_api
                                            logger.info(f"✅ [REFRESH GRUPO] JID correto encontrado via fetchAllGroups: {group_jid}")
                                            # Atualizar contact_phone com JID correto
                                            conversation.contact_phone = group_jid
                                            conversation.save(update_fields=['contact_phone'])
                                            break
                                
                                # Se não encontrou por nome, tentar usar o primeiro grupo (fallback)
                                if not group_jid and all_groups:
                                    first_group = all_groups[0]
                                    potential_jid = first_group.get('id', '')
                                    if potential_jid.endswith('@g.us'):
                                        logger.warning(f"⚠️ [REFRESH GRUPO] Usando primeiro grupo da lista como fallback: {potential_jid}")
                                        group_jid = potential_jid
                except Exception as e:
                    logger.warning(f"⚠️ [REFRESH GRUPO] Erro ao buscar via fetchAllGroups: {e}")
                
                # Se não encontrou via fetchAllGroups, tentar usar contact_phone ou mensagens recentes
                if not group_jid:
                    # ✅ VALIDAÇÃO CRÍTICA: Verificar se contact_phone termina com @lid (grupo usa LID)
                    if raw_phone.endswith('@lid'):
                        logger.warning(f"⚠️ [REFRESH GRUPO] contact_phone é LID: {raw_phone}, tentando buscar JID real de mensagens recentes...")
                        
                        # ✅ MELHORIA: Tentar buscar JID real do grupo de mensagens recentes
                        from apps.chat.models import Message
                        recent_message = Message.objects.filter(
                            conversation=conversation,
                            direction='incoming'
                        ).order_by('-created_at').first()
                        
                        if recent_message and recent_message.metadata:
                            message_metadata = recent_message.metadata or {}
                            remote_jid = message_metadata.get('remoteJid') or message_metadata.get('remote_jid')
                            
                            if remote_jid and '@g.us' in remote_jid:
                                group_jid = remote_jid
                                logger.info(f"✅ [REFRESH GRUPO] group_jid encontrado em mensagem recente: {group_jid}")
                            else:
                                # Não encontrou JID real, retornar dados do cache
                                logger.warning(f"⚠️ [REFRESH GRUPO] Não foi possível extrair JID real")
                                group_metadata = conversation.group_metadata or {}
                                return Response({
                                    'message': 'Grupo usa LID - retornando dados do cache',
                                    'conversation': ConversationSerializer(conversation).data,
                                    'warning': 'group_uses_lid',
                                    'from_cache': True
                                })
                        else:
                            # Não encontrou mensagens recentes, retornar dados do cache
                            logger.warning(f"⚠️ [REFRESH GRUPO] Não há mensagens recentes para extrair JID real")
                            group_metadata = conversation.group_metadata or {}
                            return Response({
                                'message': 'Grupo usa LID - retornando dados do cache',
                                'conversation': ConversationSerializer(conversation).data,
                                'warning': 'group_uses_lid',
                                'from_cache': True
                            })
                    else:
                        # ✅ USAR JID COMPLETO - Evolution API aceita:
                        # - Grupos: xxx@g.us
                        if '@g.us' in raw_phone:
                            group_jid = raw_phone
                        elif '@s.whatsapp.net' in raw_phone:
                            group_jid = raw_phone.replace('@s.whatsapp.net', '@g.us')
                        else:
                            clean_id = raw_phone.replace('+', '').strip()
                            group_jid = f"{clean_id}@g.us"
                
                # ✅ VALIDAÇÃO FINAL: Verificar se group_jid termina com @lid (não é válido para API)
                if group_jid and group_jid.endswith('@lid'):
                    logger.warning(f"⚠️ [REFRESH GRUPO] group_jid é LID: {group_jid}, retornando dados do cache")
                    group_metadata = conversation.group_metadata or {}
                    return Response({
                        'message': 'Grupo usa LID - retornando dados do cache',
                        'conversation': ConversationSerializer(conversation).data,
                        'warning': 'group_uses_lid',
                        'from_cache': True
                    })
                
                endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                
                logger.info(f"🔄 [REFRESH GRUPO] Buscando info do grupo {group_jid}")
                logger.info(f"   Raw phone: {raw_phone}")
                logger.info(f"   Formatted JID: {group_jid}")
                
                request_start = time.perf_counter()
                
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        endpoint,
                        params={'groupJid': group_jid},
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        group_info = response.json()
                        record_latency(
                            'refresh_info_group',
                            time.perf_counter() - request_start,
                            {
                                'conversation_id': str(conversation.id),
                                'instance_name': instance_name,
                                'status_code': response.status_code,
                            }
                        )
                        
                        # Extrair dados
                        group_name = group_info.get('subject', '')
                        group_pic_url = group_info.get('pictureUrl')
                        participants_count = group_info.get('size', 0)
                        group_desc = group_info.get('desc', '')
                        
                        # ✅ NOVO: Buscar participantes do grupo para suporte a menções
                        participants_list = []
                        try:
                            participants_endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                            participants_response = client.get(
                                participants_endpoint,
                                params={'groupJid': group_jid, 'getParticipants': 'true'},
                                headers=headers,
                                timeout=15.0  # Timeout maior para buscar participantes
                            )
                            
                            if participants_response.status_code == 200:
                                participants_data = participants_response.json()
                                
                                # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                                import json
                                logger.critical(f"📦 [REFRESH GRUPO API] JSON COMPLETO retornado por findGroupInfos com getParticipants=true:")
                                logger.critical(f"   {json.dumps(participants_data, indent=2, ensure_ascii=False)}")
                                
                                raw_participants = participants_data.get('participants', [])
                                
                                # ✅ CORREÇÃO CRÍTICA: Processar participantes usando phoneNumber (telefone real)
                                # Formato da resposta: {"id": "@lid", "phoneNumber": "@s.whatsapp.net", "admin": "..."}
                                for participant in raw_participants:
                                    participant_id = participant.get('id') or participant.get('jid') or ''
                                    participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number') or ''
                                    
                                    logger.info(f"   🔍 [REFRESH GRUPO] Processando participante: id={participant_id}, phoneNumber={participant_phone_number}")
                                    
                                    # ✅ PRIORIDADE: Usar phoneNumber (telefone real) primeiro
                                    phone_raw = None
                                    if participant_phone_number:
                                        # Extrair telefone do phoneNumber (formato: 5517996196795@s.whatsapp.net)
                                        phone_raw = participant_phone_number.split('@')[0]
                                        logger.info(f"   ✅ [REFRESH GRUPO] Telefone extraído de phoneNumber: {phone_raw}")
                                    elif participant_id and not participant_id.endswith('@lid'):
                                        # Fallback: usar id apenas se não for LID
                                        if '@' in participant_id and participant_id.endswith('@s.whatsapp.net'):
                                            phone_raw = participant_id.split('@')[0]
                                            logger.info(f"   ✅ [REFRESH GRUPO] Telefone extraído de id: {phone_raw}")
                                    
                                    # Se não encontrou telefone válido, pular
                                    if not phone_raw:
                                        logger.warning(f"   ⚠️ [REFRESH GRUPO] Participante sem phoneNumber válido: id={participant_id}")
                                        continue
                                    
                                    # Normalizar telefone para E.164
                                    from apps.contacts.models import Contact
                                    from apps.contacts.signals import normalize_phone_for_search
                                    from apps.notifications.services import normalize_phone
                                    
                                    normalized_phone = normalize_phone(phone_raw)
                                    if not normalized_phone:
                                        normalized_phone = phone_raw
                                    
                                    # Buscar contato na base de dados usando telefone real
                                    normalized_phone_for_search = normalize_phone_for_search(normalized_phone)
                                    contact = Contact.objects.filter(
                                        tenant=conversation.tenant,
                                        phone__in=[normalized_phone_for_search, normalized_phone, phone_raw, f"+{phone_raw}"]
                                    ).first()
                                    
                                    # ✅ CORREÇÃO: Prioridade: nome do contato > pushname da Evolution API > telefone formatado
                                    participant_name = ''
                                    if contact and contact.name:
                                        participant_name = contact.name
                                        logger.info(f"   ✅ [REFRESH GRUPO] Nome do contato encontrado: {participant_name}")
                                    else:
                                        # Se não encontrou contato cadastrado, buscar pushname da Evolution API
                                        logger.info(f"   🔍 [REFRESH GRUPO] Contato não encontrado, buscando pushname na Evolution API...")
                                        # ✅ CORREÇÃO: Usar wa_instance ao invés de instance
                                        pushname = fetch_pushname_from_evolution(wa_instance, normalized_phone)
                                        if pushname:
                                            participant_name = pushname
                                            logger.info(f"   ✅ [REFRESH GRUPO] Pushname encontrado via Evolution API: {participant_name}")
                                        else:
                                            logger.info(f"   ℹ️ [REFRESH GRUPO] Pushname não encontrado, name vazio (telefone será mostrado)")
                                    
                                    participant_info = {
                                        'phone': normalized_phone,  # Telefone real normalizado E.164
                                        'name': participant_name,  # Nome do contato ou vazio
                                        'jid': participant_id,  # LID original
                                        'phoneNumber': participant_phone_number  # JID real do telefone
                                    }
                                    logger.info(f"   ✅ [REFRESH GRUPO] Participante processado: phone={normalized_phone}, name={participant_name}, phoneNumber={participant_phone_number}")
                                    participants_list.append(participant_info)
                                
                                logger.info(f"✅ [REFRESH GRUPO] {len(participants_list)} participantes carregados")
                            else:
                                logger.warning(f"⚠️ [REFRESH GRUPO] Erro ao buscar participantes: {participants_response.status_code}")
                        except Exception as e:
                            logger.warning(f"⚠️ [REFRESH GRUPO] Erro ao buscar participantes: {e}")
                            # Continuar sem participantes (não quebrar o refresh)
                        
                        # Atualizar conversa
                        if group_name and group_name != conversation.contact_name:
                            conversation.contact_name = group_name
                            update_fields.append('contact_name')
                            logger.info(f"✅ [REFRESH GRUPO] Nome: {group_name}")
                        
                        if group_pic_url and group_pic_url != conversation.profile_pic_url:
                            conversation.profile_pic_url = group_pic_url
                            update_fields.append('profile_pic_url')
                            logger.info(f"✅ [REFRESH GRUPO] Foto atualizada")
                        
                        # Atualizar metadados (incluindo participantes)
                        # ✅ CRÍTICO: Limpar participantes antes de salvar (remover LIDs do phone)
                        cleaned_participants = clean_participants_for_metadata(participants_list)
                        conversation.group_metadata = {
                            'group_id': group_jid,
                            'group_name': group_name,
                            'group_pic_url': group_pic_url,
                            'participants_count': participants_count,
                            'description': group_desc,
                            'is_group': True,
                            'participants': cleaned_participants,  # ✅ NOVO: Lista de participantes limpa (sem LIDs)
                            'participants_updated_at': timezone.now().isoformat(),  # ✅ NOVO: Timestamp de atualização
                        }
                        update_fields.append('group_metadata')
                    elif response.status_code == 404:
                        # Grupo não encontrado (pode ter sido deletado ou instância saiu)
                        logger.warning(f"⚠️ [REFRESH GRUPO] Grupo não encontrado (404) - pode ter sido deletado ou instância não tem acesso")
                        logger.warning(f"   JID: {group_jid}")
                        logger.warning(f"   Instance: {instance_name}")
                        record_error('refresh_info_group', f'404 {group_jid}')
                        
                        # Retornar sucesso mas com aviso (não quebrar UI)
                        return Response({
                            'message': 'Grupo não encontrado - pode ter sido deletado ou instância não tem acesso',
                            'conversation': ConversationSerializer(conversation).data,
                            'warning': 'group_not_found',
                            'from_cache': False
                        })
                    else:
                        logger.error(f"❌ [REFRESH GRUPO] Erro API: {response.status_code}")
                        logger.error(f"   Response: {response.text[:200]}")
                        record_error('refresh_info_group', f'{response.status_code} response')
                        return Response(
                            {'error': f'Erro ao buscar grupo: {response.status_code}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
            
            # 👤 CONTATOS INDIVIDUAIS: Endpoint /chat/fetchProfilePictureUrl
            else:
                clean_phone = conversation.contact_phone.replace('+', '').replace('@s.whatsapp.net', '')
                endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance_name}"
                
                logger.info(f"🔄 [REFRESH CONTATO] Buscando foto do contato {clean_phone}")
                request_start = time.perf_counter()
                
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        endpoint,
                        params={'number': clean_phone},
                        headers=headers
                    )
                    record_latency(
                        'refresh_info_contact',
                        time.perf_counter() - request_start,
                        {
                            'conversation_id': str(conversation.id),
                            'instance_name': instance_name,
                            'status_code': response.status_code,
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        profile_url = (
                            data.get('profilePictureUrl') or
                            data.get('profilePicUrl') or
                            data.get('url') or
                            data.get('picture')
                        )
                        
                        if profile_url and profile_url != conversation.profile_pic_url:
                            conversation.profile_pic_url = profile_url
                            update_fields.append('profile_pic_url')
                            logger.info(f"✅ [REFRESH CONTATO] Foto atualizada")
                        elif not profile_url:
                            logger.info(f"ℹ️ [REFRESH CONTATO] Foto não disponível")
                    elif response.status_code == 404:
                        # ✅ CORREÇÃO: 404 é esperado se contato não tem foto de perfil
                        logger.debug("ℹ️ [REFRESH CONTATO] Contato não tem foto de perfil (404) - normal")
                        record_error('refresh_info_contact', '404 profile picture')
                    else:
                        logger.warning(f"⚠️ [REFRESH CONTATO] Erro API: {response.status_code}")
                        record_error('refresh_info_contact', f'{response.status_code} response')
            
            # Salvar alterações + metadata (timestamp do refresh)
            refresh_timestamp = timezone.now().isoformat()
            metadata['last_refresh_at'] = refresh_timestamp
            conversation.metadata = metadata
            if update_fields:
                if 'metadata' not in update_fields:
                    update_fields.append('metadata')
            else:
                update_fields = ['metadata']
            conversation.save(update_fields=update_fields)
            logger.info(f"✅ [REFRESH] {len(update_fields)} campos atualizados (incluindo metadata)")
            
            # ✅ MELHORIA: Invalidar cache de participantes se group_metadata foi atualizado
            if 'group_metadata' in update_fields and conversation.conversation_type == 'group':
                participants_cache_key = f"group_participants:{conversation.id}"
                cache.delete(participants_cache_key)
                logger.info(f"🗑️ [REFRESH] Cache de participantes invalidado para conversa {conversation.id}")
            
            # Salvar no cache por 5min
            cache.set(cache_key, True, REFRESH_INFO_CACHE_SECONDS)
            
            # Broadcast atualização via WebSocket
            if update_fields:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                
                channel_layer = get_channel_layer()
                if channel_layer:
                    serializer = ConversationSerializer(conversation)
                    async_to_sync(channel_layer.group_send)(
                        f"tenant_{request.user.tenant.id}",
                        {
                            'type': 'conversation_updated',
                            'conversation': serializer.data
                        }
                    )
            
            return Response({
                'message': f'Informações {"do grupo" if conversation.conversation_type == "group" else "do contato"} atualizadas com sucesso',
                'conversation': ConversationSerializer(conversation).data,
                'updated_fields': update_fields,
                'from_cache': False
            })
        
        except httpx.TimeoutException:
            logger.error(f"⏱️ [REFRESH] Timeout ao buscar {conversation.id}")
            record_error('refresh_info_timeout', f'timeout conversation {conversation.id}')
            return Response(
                {'error': 'Timeout ao buscar informações da Evolution API'},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as e:
            logger.error(f"❌ [REFRESH] Erro: {e}", exc_info=True)
            record_error('refresh_info_unexpected', str(e))
            return Response(
                {'error': f'Erro ao atualizar informações da conversa'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='group-info')
    def group_info(self, request, pk=None):
        """
        Retorna informações detalhadas do grupo:
        - Data de criação
        - Lista de participantes (com nomes)
        - Administradores do grupo
        
        Funciona apenas para conversas do tipo 'group'.
        """
        import httpx
        from datetime import datetime
        from apps.contacts.models import Contact
        import re
        
        def format_phone_for_display(phone: str) -> str:
            """Formata telefone para exibição: (11) 99999-9999"""
            if not phone:
                return phone
            
            # Remover tudo exceto números
            clean = re.sub(r'\D', '', phone)
            
            # Remover código do país (55) se presente
            digits = clean
            if clean.startswith('55') and len(clean) >= 12:
                digits = clean[2:]
            
            # Formatar baseado no tamanho
            if len(digits) == 11:
                return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
            elif len(digits) == 10:
                return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
            
            return phone  # Retornar original se não conseguir formatar
        
        conversation = self.get_object()
        
        # Validar que é um grupo
        if conversation.conversation_type != 'group':
            return Response(
                {'error': 'Esta conversa não é um grupo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar instância WhatsApp ativa
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            return Response(
                {'error': 'Nenhuma instância WhatsApp ativa encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Buscar configuração do servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            return Response(
                {'error': 'Servidor Evolution não configurado'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Preparar configuração
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        # Montar group_jid
        raw_phone = conversation.contact_phone
        if '@g.us' in raw_phone:
            group_jid = raw_phone
        elif '@s.whatsapp.net' in raw_phone:
            group_jid = raw_phone.replace('@s.whatsapp.net', '@g.us')
        else:
            clean_id = raw_phone.replace('+', '').strip()
            group_jid = f"{clean_id}@g.us"
        
        # ✅ VALIDAÇÃO: Se group_jid termina com @lid, não tentar buscar (grupo usa LID)
        # ✅ CORREÇÃO: @g.us = grupo válido, não é LID. Apenas @lid é LID.
        if group_jid.endswith('@lid'):
            logger.warning(f"⚠️ [GROUP INFO] group_jid é LID: {group_jid}, retornando dados do metadata")
            # Retornar dados do metadata se disponíveis
            group_metadata = conversation.group_metadata or {}
            participants_from_metadata = group_metadata.get('participants', [])
            
            return Response({
                'group_id': group_jid,
                'group_name': conversation.contact_name or group_metadata.get('group_name', 'Grupo WhatsApp'),
                'group_pic_url': conversation.profile_pic_url or group_metadata.get('group_pic_url'),
                'description': group_metadata.get('description', ''),
                'participants_count': len(participants_from_metadata),
                'creation_date': None,  # Não disponível para grupos com LID
                'participants': clean_participants_for_metadata(participants_from_metadata),
                'admins': [],  # Não disponível para grupos com LID
                'uses_lid': True,
                'warning': 'Grupo usa LID - algumas informações podem não estar disponíveis'
            })
        
        try:
            endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
            
            logger.info(f"🔍 [GROUP INFO] Buscando informações detalhadas do grupo {group_jid}")
            
            with httpx.Client(timeout=15.0) as client:
                # Buscar informações completas do grupo (com participantes e admins)
                response = client.get(
                    endpoint,
                    params={'groupJid': group_jid, 'getParticipants': 'true'},
                    headers=headers
                )
                
                if response.status_code == 200:
                    group_data = response.json()
                    
                    # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                    import json
                    logger.critical(f"📦 [GROUP INFO API] JSON COMPLETO retornado por findGroupInfos:")
                    logger.critical(f"   {json.dumps(group_data, indent=2, ensure_ascii=False)}")
                    
                    # Extrair informações básicas
                    group_name = group_data.get('subject', conversation.contact_name or 'Grupo WhatsApp')
                    group_pic_url = group_data.get('pictureUrl') or conversation.profile_pic_url
                    description = group_data.get('desc', '')
                    participants_count = group_data.get('size', 0)
                    
                    # ✅ Data de criação (se disponível)
                    creation_timestamp = group_data.get('creation') or group_data.get('creationTime')
                    creation_date = None
                    if creation_timestamp:
                        try:
                            # Timestamp pode ser em segundos ou milissegundos
                            if isinstance(creation_timestamp, (int, float)):
                                if creation_timestamp > 1e10:  # Milissegundos
                                    creation_timestamp = creation_timestamp / 1000
                                creation_date = datetime.fromtimestamp(creation_timestamp, tz=timezone.utc).isoformat()
                        except (ValueError, OSError) as e:
                            logger.warning(f"⚠️ [GROUP INFO] Erro ao converter timestamp de criação: {e}")
                    
                    # ✅ Processar participantes
                    raw_participants = group_data.get('participants', [])
                    participants_list = []
                    admins_list = []
                    
                    # ✅ CORREÇÃO CRÍTICA: Processar participantes usando phoneNumber (telefone real)
                    # Formato da resposta: {"id": "@lid", "phoneNumber": "@s.whatsapp.net", "admin": "..."}
                    participants_list = []
                    admins_list = []
                    
                    # Primeiro, coletar todos os telefones reais para busca em batch
                    all_phones = []
                    for participant in raw_participants:
                        participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number') or ''
                        if participant_phone_number:
                            phone_raw = participant_phone_number.split('@')[0]
                            if phone_raw and not is_lid_number(phone_raw):
                                all_phones.append(phone_raw)
                    
                    # Buscar contatos em batch usando telefones reais
                    contacts_map = {}
                    if all_phones:
                        from apps.contacts.signals import normalize_phone_for_search
                        from apps.notifications.services import normalize_phone
                        normalized_phones = []
                        for p in all_phones:
                            normalized = normalize_phone(p)
                            if normalized:
                                normalized_phones.append(normalized)
                                normalized_phones.append(normalize_phone_for_search(normalized))
                        
                        contacts = Contact.objects.filter(
                            tenant=conversation.tenant,
                            phone__in=normalized_phones + all_phones
                        ).values('phone', 'name')
                        
                        for contact in contacts:
                            normalized_contact_phone = normalize_phone_for_search(contact['phone'])
                            contacts_map[normalized_contact_phone] = contact.get('name', '')
                            # Também mapear telefone normalizado
                            from apps.notifications.services import normalize_phone
                            phone_normalized = normalize_phone(contact['phone'])
                            if phone_normalized:
                                contacts_map[normalize_phone_for_search(phone_normalized)] = contact.get('name', '')
                    
                    # Processar cada participante usando phoneNumber
                    for participant in raw_participants:
                        participant_id = participant.get('id') or participant.get('jid') or ''
                        participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number') or ''
                        
                        logger.info(f"   🔍 [GROUP INFO] Processando participante: id={participant_id}, phoneNumber={participant_phone_number}")
                        
                        # ✅ PRIORIDADE: Usar phoneNumber (telefone real) primeiro
                        phone_raw = None
                        if participant_phone_number:
                            # Extrair telefone do phoneNumber (formato: 5517996196795@s.whatsapp.net)
                            phone_raw = participant_phone_number.split('@')[0]
                            logger.info(f"   ✅ [GROUP INFO] Telefone extraído de phoneNumber: {phone_raw}")
                        elif participant_id and not participant_id.endswith('@lid'):
                            # Fallback: usar id apenas se não for LID
                            if '@' in participant_id and participant_id.endswith('@s.whatsapp.net'):
                                phone_raw = participant_id.split('@')[0]
                                logger.info(f"   ✅ [GROUP INFO] Telefone extraído de id: {phone_raw}")
                        
                        # Se não encontrou telefone válido, pular
                        if not phone_raw:
                            logger.warning(f"   ⚠️ [GROUP INFO] Participante sem phoneNumber válido: id={participant_id}")
                            continue
                        
                        # Normalizar telefone para E.164
                        from apps.notifications.services import normalize_phone
                        normalized_phone = normalize_phone(phone_raw)
                        if not normalized_phone:
                            normalized_phone = phone_raw
                        
                        # Verificar se é admin
                        is_admin = participant.get('isAdmin', False) or participant.get('admin', False)
                        
                        # Buscar nome do contato usando telefone real
                        from apps.contacts.signals import normalize_phone_for_search
                        normalized_phone_for_search = normalize_phone_for_search(normalized_phone)
                        contact_name = contacts_map.get(normalized_phone_for_search) or contacts_map.get(normalized_phone) or contacts_map.get(phone_raw)
                        
                        # ✅ CORREÇÃO: Prioridade: nome do contato > pushname da Evolution API > telefone formatado
                        participant_name = ''
                        if contact_name:
                            participant_name = contact_name
                            logger.info(f"   ✅ [GROUP INFO] Nome do contato encontrado: {participant_name}")
                        else:
                            # Se não encontrou contato cadastrado, buscar pushname da Evolution API
                            logger.info(f"   🔍 [GROUP INFO] Contato não encontrado, buscando pushname na Evolution API...")
                            pushname = fetch_pushname_from_evolution(wa_instance, normalized_phone)
                            if pushname:
                                participant_name = pushname
                                logger.info(f"   ✅ [GROUP INFO] Pushname encontrado via Evolution API: {participant_name}")
                            else:
                                logger.info(f"   ℹ️ [GROUP INFO] Pushname não encontrado, name vazio (telefone será mostrado)")
                        
                        participant_info = {
                            'jid': participant_id,  # LID original
                            'phone': normalized_phone,  # Telefone real normalizado E.164
                            'name': participant_name,  # Nome do contato ou vazio
                            'phoneNumber': participant_phone_number,  # JID real do telefone
                            'is_admin': is_admin
                        }
                        logger.info(f"   ✅ [GROUP INFO] Participante processado: phone={normalized_phone}, name={participant_name}, phoneNumber={participant_phone_number}")
                        
                        participants_list.append(participant_info)
                        
                        if is_admin:
                            admins_list.append(participant_info)
                    
                    # Ordenar participantes: admins primeiro, depois por nome
                    participants_list.sort(key=lambda p: (not p['is_admin'], p['name'].lower()))
                    
                    logger.info(f"✅ [GROUP INFO] {len(participants_list)} participantes processados ({len(admins_list)} admins)")
                    
                    return Response({
                        'group_id': group_jid,
                        'group_name': group_name,
                        'group_pic_url': group_pic_url,
                        'description': description,
                        'participants_count': len(participants_list),
                        'creation_date': creation_date,
                        'participants': participants_list,
                        'admins': admins_list,
                        'uses_lid': False
                    })
                    
                elif response.status_code == 404:
                    logger.warning(f"⚠️ [GROUP INFO] Grupo não encontrado (404): {group_jid}")
                    # Retornar dados do metadata se disponíveis
                    group_metadata = conversation.group_metadata or {}
                    participants_from_metadata = group_metadata.get('participants', [])
                    
                    return Response({
                        'group_id': group_jid,
                        'group_name': conversation.contact_name or group_metadata.get('group_name', 'Grupo WhatsApp'),
                        'group_pic_url': conversation.profile_pic_url or group_metadata.get('group_pic_url'),
                        'description': group_metadata.get('description', ''),
                        'participants_count': len(participants_from_metadata),
                        'creation_date': None,
                        'participants': clean_participants_for_metadata(participants_from_metadata),
                        'admins': [],
                        'uses_lid': False,
                        'warning': 'Grupo não encontrado na Evolution API - retornando dados do cache'
                    })
                else:
                    logger.error(f"❌ [GROUP INFO] Erro API: {response.status_code}")
                    return Response(
                        {'error': f'Erro ao buscar informações do grupo: {response.status_code}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        
        except httpx.TimeoutException:
            logger.error(f"⏱️ [GROUP INFO] Timeout ao buscar grupo {group_jid}")
            return Response(
                {'error': 'Timeout ao buscar informações do grupo'},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as e:
            logger.error(f"❌ [GROUP INFO] Erro: {e}", exc_info=True)
            return Response(
                {'error': f'Erro ao buscar informações do grupo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def start(self, request):
        """
        Inicia uma nova conversa com um contato.
        Body: { 
            "contact_phone": "+5517999999999", 
            "contact_name": "João Silva" (opcional),
            "department": "uuid" (opcional, usa o primeiro se não informado)
        }
        """
        contact_phone = request.data.get('contact_phone')
        contact_name = request.data.get('contact_name', '')
        department_id = request.data.get('department')
        
        if not contact_phone:
            return Response(
                {'error': 'contact_phone é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalizar telefone (remover espaços, garantir +)
        contact_phone = contact_phone.strip()
        if not contact_phone.startswith('+'):
            contact_phone = f'+{contact_phone}'
        
        # Selecionar departamento
        # ✅ CORREÇÃO: Se department_id não for fornecido, criar conversa sem departamento (Inbox)
        # Não usar departamento padrão para respeitar a seleção do usuário
        from apps.authn.models import Department
        department = None
        if department_id:
            try:
                department = Department.objects.get(
                    id=department_id,
                    tenant=request.user.tenant
                )
                logger.info(f"📋 [CONVERSATION START] Departamento selecionado: {department.name} (ID: {department.id})")
            except Department.DoesNotExist:
                return Response(
                    {'error': 'Departamento não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # ✅ CORREÇÃO: Se não especificado, criar sem departamento (Inbox)
            logger.info(f"📋 [CONVERSATION START] Nenhum departamento especificado - criando no Inbox")
        
        # ✅ CORREÇÃO: Normalizar telefone antes de buscar/criar para evitar duplicatas
        from apps.contacts.signals import normalize_phone_for_search
        
        normalized_phone = normalize_phone_for_search(contact_phone)
        
        # Verificar se já existe conversa (usando telefone normalizado OU original)
        # ✅ CORREÇÃO: Usar Q() para tudo para evitar erro de sintaxe (keyword + positional)
        existing = Conversation.objects.filter(
            Q(tenant=request.user.tenant) &
            (Q(contact_phone=normalized_phone) | Q(contact_phone=contact_phone))
        ).first()
        
        if existing:
            # Se telefone está em formato diferente, atualizar para formato normalizado
            if existing.contact_phone != normalized_phone:
                logger.info(
                    f"🔄 [NORMALIZAÇÃO API] Atualizando telefone da conversa {existing.id}: "
                    f"{existing.contact_phone} → {normalized_phone}"
                )
                existing.contact_phone = normalized_phone
                existing.save(update_fields=['contact_phone'])
            
            # ✅ CORREÇÃO CRÍTICA: Se conversa estava fechada, reabrir automaticamente
            # Isso garante que conversas fechadas sejam reabertas quando usuário inicia nova conversa
            needs_update = False
            update_fields_list = []
            
            if existing.status == 'closed':
                old_status = existing.status
                old_department = existing.department.name if existing.department else 'Nenhum'
                
                # ✅ CORREÇÃO: Quando reabrir, usar o department enviado (ou None se Inbox)
                # Se department foi enviado, usar ele. Senão, remover para voltar ao Inbox
                if department:
                    existing.department = department
                    existing.status = 'open'
                    logger.info(f"🔄 [CONVERSATION START] Conversa {normalized_phone} reaberta com department: {department.name}")
                else:
                    # Sem department, remover departamento para voltar ao Inbox
                    existing.status = 'pending'
                    existing.department = None
                    logger.info(f"🔄 [CONVERSATION START] Conversa {normalized_phone} reaberta sem departamento (Inbox)")
                
                update_fields_list.extend(['status', 'department'])
                needs_update = True
                
                status_str = existing.department.name if existing.department else "Inbox"
                logger.info(f"🔄 [CONVERSATION START] Conversa reaberta: {old_status} → {existing.status}")
                logger.info(f"   📋 Departamento: {old_department} → {status_str}")
            
            # ✅ CORREÇÃO: Se department foi enviado mas conversa tem department diferente, atualizar
            if department and existing.department != department:
                existing.department = department
                # Se estava pending, mudar para open ao atribuir departamento
                if existing.status == 'pending':
                    existing.status = 'open'
                    update_fields_list.append('status')
                update_fields_list.append('department')
                needs_update = True
                logger.info(f"🔄 [CONVERSATION START] Departamento atualizado: {existing.department.name if existing.department else 'Nenhum'} → {department.name}")
            
            # ✅ CORREÇÃO: Atualizar nome se fornecido e diferente
            if contact_name and existing.contact_name != contact_name:
                existing.contact_name = contact_name
                update_fields_list.append('contact_name')
                needs_update = True
                logger.info(f"🔄 [CONVERSATION START] Nome atualizado: {existing.contact_name} → {contact_name}")
            
            if needs_update:
                existing.save(update_fields=update_fields_list)
                logger.info(f"✅ [CONVERSATION START] Conversa existente atualizada: {existing.id}")
            
            # ✅ CORREÇÃO CRÍTICA: Atualizar last_message_at para conversa aparecer no topo da lista
            # Isso garante que conversas reabertas apareçam no topo, igual ao comportamento do webhook
            existing.update_last_message()
            logger.info(f"✅ [CONVERSATION START] last_message_at atualizado para conversa aparecer no topo")
            
            # ✅ CORREÇÃO CRÍTICA: Broadcast conversation_updated mesmo para conversas existentes
            # Isso garante que a conversa apareça na lista se estava fechada
            try:
                from apps.chat.utils.websocket import broadcast_conversation_updated
                from django.db import transaction
                
                def do_broadcast():
                    try:
                        broadcast_conversation_updated(existing, request=request)
                        logger.critical(f"✅ [CONVERSATION START] conversation_updated enviado para conversa existente")
                    except Exception as e:
                        logger.critical(f"❌ [CONVERSATION START] Erro no broadcast após commit: {e}", exc_info=True)
                
                if transaction.get_connection().in_atomic_block:
                    transaction.on_commit(do_broadcast)
                    logger.critical(f"⏳ [CONVERSATION START] Broadcast agendado para após commit da transação")
                else:
                    do_broadcast()
            except Exception as e:
                logger.critical(f"❌ [CONVERSATION START] Erro ao configurar broadcast para conversa existente: {e}", exc_info=True)
            
            return Response(
                {
                    'message': 'Conversa já existe',
                    'conversation': ConversationSerializer(existing).data
                },
                status=status.HTTP_200_OK
            )
        
        # Criar nova conversa com telefone normalizado
        # ✅ CORREÇÃO: Se sem departamento (Inbox), status deve ser 'pending'
        # Se com departamento, status pode ser 'open'
        initial_status = 'pending' if not department else 'open'
        
        conversation = Conversation.objects.create(
            tenant=request.user.tenant,
            department=department,
            contact_phone=normalized_phone,  # ✅ Usar telefone normalizado
            contact_name=contact_name,
            assigned_to=request.user,
            status=initial_status
        )
        
        logger.info(f"✅ [CONVERSATION START] Conversa criada: ID={conversation.id}, Status={initial_status}, Department={department.name if department else 'Inbox'}")
        
        # Adicionar usuário como participante
        conversation.participants.add(request.user)
        
        # ✅ CORREÇÃO CRÍTICA: Atualizar last_message_at para conversa aparecer no topo da lista
        # Isso garante que novas conversas apareçam no topo, igual ao comportamento do webhook
        conversation.update_last_message()
        logger.info(f"✅ [CONVERSATION START] last_message_at atualizado para nova conversa aparecer no topo")
        
        # ✅ CORREÇÃO CRÍTICA: Broadcast conversation_updated para aparecer na lista de conversas
        # IMPORTANTE: Usar transaction.on_commit() para garantir que broadcast acontece APÓS commit
        # Isso garante que a conversa e participants estejam visíveis no banco quando o broadcast ler
        try:
            from apps.chat.utils.websocket import broadcast_conversation_updated
            from django.db import transaction
            
            # ✅ DEBUG: Log detalhado antes do broadcast
            logger.critical(f"📡 [CONVERSATION START] Preparando broadcast conversation_updated")
            logger.critical(f"   🆔 Conversation ID: {conversation.id}")
            logger.critical(f"   📋 Departamento: {conversation.department.name if conversation.department else 'Nenhum (Inbox)'}")
            logger.critical(f"   📊 Status: {conversation.status}")
            logger.critical(f"   👤 Contact Name: {conversation.contact_name}")
            logger.critical(f"   📞 Contact Phone: {conversation.contact_phone}")
            
            def do_broadcast():
                try:
                    # ✅ FIX CRÍTICO: Usar broadcast_conversation_updated que já faz prefetch de last_message
                    broadcast_conversation_updated(conversation, request=request)
                    logger.critical(f"✅ [CONVERSATION START] conversation_updated enviado para aparecer na lista")
                except Exception as e:
                    logger.critical(f"❌ [CONVERSATION START] Erro no broadcast após commit: {e}", exc_info=True)
            
            # ✅ CORREÇÃO CRÍTICA: Executar broadcast após commit da transação
            # Isso garante que a conversa e participants estejam disponíveis no banco quando buscamos
            # Se não estamos em uma transação ativa, executar imediatamente
            if transaction.get_connection().in_atomic_block:
                transaction.on_commit(do_broadcast)
                logger.critical(f"⏳ [CONVERSATION START] Broadcast agendado para após commit da transação")
            else:
                # Não estamos em transação, executar imediatamente
                do_broadcast()
        except Exception as e:
            logger.critical(f"❌ [CONVERSATION START] Erro ao configurar broadcast conversation_updated: {e}", exc_info=True)
        
        return Response(
            {
                'message': 'Conversa criada com sucesso!',
                'conversation': ConversationSerializer(conversation).data
            },
            status=status.HTTP_201_CREATED
        )
    
    def _format_phone_for_display(self, phone: str) -> str:
        """Formata telefone para exibição (como WhatsApp faz)."""
        import re
        clean = re.sub(r'\D', '', phone)
        if clean.startswith('55') and len(clean) >= 12:
            clean = clean[2:]  # Remover código do país
        if len(clean) == 11:
            return f"({clean[0:2]}) {clean[2:7]}-{clean[7:11]}"
        elif len(clean) == 10:
            return f"({clean[0:2]}) {clean[2:6]}-{clean[6:10]}"
        elif len(clean) == 9:
            return f"{clean[0:5]}-{clean[5:9]}"
        elif len(clean) == 8:
            return f"{clean[0:4]}-{clean[4:8]}"
        return clean[:15] if clean else phone
    
    @action(detail=True, methods=['get'], url_path='participants')
    def get_participants(self, request, pk=None):
        """
        Lista participantes do grupo (para suporte a menções).
        
        Retorna lista de participantes com nome e telefone.
        Tenta buscar do group_metadata primeiro, depois da API diretamente.
        Usa cache Redis com TTL de 5 minutos para melhor performance.
        """
        from django.core.cache import cache
        
        conversation = self.get_object()
        
        logger.critical(f"🔍 [PARTICIPANTS] ====== INICIANDO get_participants ======")
        logger.critical(f"   Conversation ID: {conversation.id}")
        logger.critical(f"   Conversation Type: {conversation.conversation_type}")
        logger.critical(f"   Contact Phone: {conversation.contact_phone}")
        logger.critical(f"   Instance Name: {conversation.instance_name}")
        
        if conversation.conversation_type != 'group':
            logger.warning(f"⚠️ [PARTICIPANTS] Não é grupo, retornando erro")
            return Response(
                {'error': 'Apenas grupos têm participantes'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ MELHORIA: Cache de participantes (5 minutos)
        cache_key = f"group_participants:{conversation.id}"
        cached_participants = cache.get(cache_key)
        
        if cached_participants is not None:
            logger.critical(f"✅ [PARTICIPANTS] Cache encontrado: {len(cached_participants)} participantes")
            # ✅ CRÍTICO: Limpar participantes do cache também (pode ter LIDs antigos)
            cleaned_cached_participants = clean_participants_for_metadata(cached_participants)
            
            # ✅ NOVO: Enriquecer participantes do cache com informações de contatos cadastrados
            from apps.contacts.models import Contact
            from apps.notifications.services import normalize_phone
            
            participant_phones = []
            for p in cleaned_cached_participants:
                phone = p.get('phone', '')
                if phone:
                    normalized = normalize_phone(phone)
                    if normalized:
                        participant_phones.append(normalized)
            
            contacts_map = {}
            if participant_phones:
                try:
                    contacts = Contact.objects.filter(
                        tenant=conversation.tenant,
                        phone__in=participant_phones
                    ).values('phone', 'name')
                    
                    for contact in contacts:
                        normalized_contact_phone = normalize_phone(contact['phone'])
                        if normalized_contact_phone:
                            contacts_map[normalized_contact_phone] = contact['name']
                    
                    logger.info(f"✅ [PARTICIPANTS] {len(contacts_map)} contatos cadastrados encontrados para participantes do cache")
                except Exception as e:
                    logger.warning(f"⚠️ [PARTICIPANTS] Erro ao buscar contatos do cache: {e}")
            
            # Enriquecer participantes do cache
            for p in cleaned_cached_participants:
                phone = p.get('phone', '')
                normalized_phone = normalize_phone(phone) if phone else None
                
                if normalized_phone and normalized_phone in contacts_map:
                    p['is_contact'] = True
                    p['contact_name'] = contacts_map[normalized_phone]
                else:
                    p['is_contact'] = False
                    p['contact_name'] = None
            
            group_metadata = conversation.group_metadata or {}
            logger.critical(f"✅ [PARTICIPANTS] Retornando {len(cleaned_cached_participants)} participantes do cache (enriquecidos com contatos)")
            return Response({
                'participants': cleaned_cached_participants,
                'count': len(cleaned_cached_participants),
                'group_name': group_metadata.get('group_name', conversation.contact_name),
                'cached': True
            })
        
        logger.critical(f"🔄 [PARTICIPANTS] Cache não encontrado, buscando do metadata...")
        
        # Buscar participantes do group_metadata
        conversation.refresh_from_db()  # ✅ IMPORTANTE: Recarregar do banco para ter dados atualizados
        group_metadata = conversation.group_metadata or {}
        participants_raw = group_metadata.get('participants', [])
        participants_updated_at = group_metadata.get('participants_updated_at')
        
        # ✅ NOVO: Verificar timestamp antes de buscar da API
        # Se participantes foram atualizados recentemente (< 5 min), usar do metadata e cachear
        if participants_updated_at and participants_raw:
            try:
                from dateutil.parser import parse as parse_dt
                updated_dt = parse_dt(participants_updated_at)
                if timezone.is_naive(updated_dt):
                    updated_dt = timezone.make_aware(updated_dt, timezone.utc)
                elapsed_minutes = (timezone.now() - updated_dt).total_seconds() / 60
                
                if elapsed_minutes < 5:  # Atualizado há menos de 5 minutos
                    logger.info(f"✅ [PARTICIPANTS] Usando participantes recentes ({elapsed_minutes:.1f}min atrás)")
                    participants = clean_participants_for_metadata(participants_raw)
                    
                    # ✅ NOVO: Enriquecer participantes do metadata com informações de contatos cadastrados
                    from apps.contacts.models import Contact
                    from apps.notifications.services import normalize_phone
                    
                    participant_phones = []
                    for p in participants:
                        phone = p.get('phone', '')
                        if phone:
                            normalized = normalize_phone(phone)
                            if normalized:
                                participant_phones.append(normalized)
                    
                    contacts_map = {}
                    if participant_phones:
                        try:
                            contacts = Contact.objects.filter(
                                tenant=conversation.tenant,
                                phone__in=participant_phones
                            ).values('phone', 'name')
                            
                            for contact in contacts:
                                normalized_contact_phone = normalize_phone(contact['phone'])
                                if normalized_contact_phone:
                                    contacts_map[normalized_contact_phone] = contact['name']
                            
                            logger.info(f"✅ [PARTICIPANTS] {len(contacts_map)} contatos cadastrados encontrados para participantes do metadata")
                        except Exception as e:
                            logger.warning(f"⚠️ [PARTICIPANTS] Erro ao buscar contatos do metadata: {e}")
                    
                    # Enriquecer participantes
                    for p in participants:
                        phone = p.get('phone', '')
                        normalized_phone = normalize_phone(phone) if phone else None
                        
                        if normalized_phone and normalized_phone in contacts_map:
                            p['is_contact'] = True
                            p['contact_name'] = contacts_map[normalized_phone]
                        else:
                            p['is_contact'] = False
                            p['contact_name'] = None
                    
                    # Salvar no cache
                    cache.set(cache_key, participants, 300)  # 5 minutos
                    return Response({
                        'participants': participants,
                        'count': len(participants),
                        'group_name': group_metadata.get('group_name', conversation.contact_name),
                        'cached': False,  # Não é cache Redis, mas é recente
                        'from_metadata': True
                    })
            except Exception as e:
                logger.warning(f"⚠️ [PARTICIPANTS] Erro ao verificar timestamp: {e}")
        
        logger.critical(f"📋 [PARTICIPANTS] Metadata: {len(participants_raw)} participantes encontrados")
        if participants_raw:
            logger.critical(f"   Primeiro participante: {participants_raw[0] if participants_raw else 'N/A'}")
        
        # ✅ CORREÇÃO CRÍTICA: Verificar se participantes têm apenas LIDs sem phoneNumber
        # Se sim, forçar busca da API para obter telefones reais
        has_only_lids = False
        if participants_raw:
            for p in participants_raw:
                participant_phone = p.get('phone', '')
                participant_phone_number = p.get('phoneNumber', '') or p.get('phone_number', '')
                participant_jid = p.get('jid', '')
                
                # Se phone é LID e não tem phoneNumber, precisa buscar da API
                if (is_lid_number(participant_phone) or participant_jid.endswith('@lid')) and not participant_phone_number:
                    has_only_lids = True
                    logger.warning(f"⚠️ [PARTICIPANTS] Participante com LID sem phoneNumber detectado: jid={participant_jid}, phone={participant_phone[:30] if participant_phone else 'N/A'}...")
                    break
        
        # ✅ CRÍTICO: Limpar participantes do metadata também (pode ter LIDs antigos)
        participants = clean_participants_for_metadata(participants_raw)
        
        # ✅ NOVA LÓGICA: Se participantes têm apenas LIDs sem phoneNumber, buscar da API
        if has_only_lids:
            logger.warning(f"🔄 [PARTICIPANTS] Participantes têm apenas LIDs sem phoneNumber, forçando busca da API...")
            # ✅ CRÍTICO: Invalidar cache para forçar busca fresca da API
            cache.delete(cache_key)
            logger.info(f"🗑️ [PARTICIPANTS] Cache invalidado devido a participantes com apenas LIDs")
            participants = []  # Limpar para forçar busca
        
        # Se não tem participantes, tentar buscar diretamente da API
        if not participants:
            logger.critical(f"🔄 [PARTICIPANTS] Sem participantes no metadata, buscando da API...")
            
            # ✅ CORREÇÃO: Tentar busca direta primeiro (mais rápido e confiável)
            try:
                logger.critical(f"🔄 [PARTICIPANTS] Tentando busca direta da API...")
                participants = self._fetch_participants_direct(conversation)
                logger.critical(f"📥 [PARTICIPANTS] Busca direta retornou: {len(participants) if participants else 0} participantes")
                
                # Se busca direta não trouxe participantes, tentar refresh-info como fallback
                if not participants:
                    logger.critical(f"🔄 [PARTICIPANTS] Busca direta não trouxe participantes, tentando refresh-info...")
                    refresh_response = self.refresh_info(request, pk=pk)
                    if refresh_response.status_code == 200:
                        # Verificar se refresh-info retornou warning (grupo não encontrado)
                        refresh_data = refresh_response.data
                        if refresh_data.get('warning') == 'group_not_found':
                            logger.warning(f"⚠️ [PARTICIPANTS] refresh-info: grupo não encontrado")
                        else:
                            # Refresh-info funcionou, buscar do metadata atualizado
                            conversation.refresh_from_db()
                            group_metadata = conversation.group_metadata or {}
                            participants = group_metadata.get('participants', [])
                            logger.critical(f"📥 [PARTICIPANTS] Refresh-info trouxe: {len(participants) if participants else 0} participantes")
            except Exception as e:
                # Erro na busca, logar e continuar
                logger.error(f"❌ [PARTICIPANTS] Erro ao buscar participantes: {e}", exc_info=True)
                participants = []
        
        # ✅ GARANTIA: Sempre retornar lista (nunca None)
        if not participants:
            participants = []
        
        logger.critical(f"📋 [PARTICIPANTS] Antes de limpar: {len(participants)} participantes")
        
        # ✅ NOVO: Enriquecer participantes com informações de contatos cadastrados
        # Buscar contatos cadastrados para verificar quais participantes estão na lista de contatos
        from apps.contacts.models import Contact
        from apps.notifications.services import normalize_phone
        
        # Normalizar telefones dos participantes para busca
        participant_phones = []
        for p in participants:
            phone = p.get('phone', '')
            if phone:
                normalized = normalize_phone(phone)
                if normalized:
                    participant_phones.append(normalized)
        
        # Buscar contatos cadastrados em lote (otimizado)
        contacts_map = {}
        if participant_phones:
            try:
                contacts = Contact.objects.filter(
                    tenant=conversation.tenant,
                    phone__in=participant_phones
                ).values('phone', 'name')
                
                for contact in contacts:
                    normalized_contact_phone = normalize_phone(contact['phone'])
                    if normalized_contact_phone:
                        contacts_map[normalized_contact_phone] = contact['name']
                
                logger.info(f"✅ [PARTICIPANTS] {len(contacts_map)} contatos cadastrados encontrados para {len(participant_phones)} participantes")
            except Exception as e:
                logger.warning(f"⚠️ [PARTICIPANTS] Erro ao buscar contatos cadastrados: {e}")
        
        # ✅ Enriquecer participantes com informações de contatos
        for p in participants:
            phone = p.get('phone', '')
            normalized_phone = normalize_phone(phone) if phone else None
            
            if normalized_phone and normalized_phone in contacts_map:
                p['is_contact'] = True
                p['contact_name'] = contacts_map[normalized_phone]
                logger.debug(f"   ✅ Participante {normalized_phone} é contato cadastrado: {contacts_map[normalized_phone]}")
            else:
                p['is_contact'] = False
                p['contact_name'] = None
                logger.debug(f"   ℹ️ Participante {normalized_phone if normalized_phone else phone} não é contato cadastrado")
        
        # ✅ CRÍTICO: Limpar participantes antes de salvar no cache (remover LIDs do phone)
        cleaned_participants = clean_participants_for_metadata(participants)
        
        logger.critical(f"📋 [PARTICIPANTS] Depois de limpar: {len(cleaned_participants)} participantes")
        if cleaned_participants:
            logger.critical(f"   Primeiro participante limpo: {cleaned_participants[0]}")
        
        # ✅ MELHORIA: Salvar no cache (5 minutos = 300 segundos)
        cache.set(cache_key, cleaned_participants, 300)
        logger.critical(f"✅ [PARTICIPANTS] {len(cleaned_participants)} participantes limpos salvos no cache (TTL: 5min)")
        
        logger.critical(f"✅ [PARTICIPANTS] Retornando {len(cleaned_participants)} participantes")
        logger.critical(f"   Response: participants={len(cleaned_participants)}, count={len(cleaned_participants)}, cached=False")
        
        return Response({
            'participants': cleaned_participants,
            'count': len(cleaned_participants),
            'group_name': group_metadata.get('group_name', conversation.contact_name),
            'cached': False
        })
    
    def _fetch_participants_direct(self, conversation):
        """
        Busca participantes diretamente da Evolution API, sem passar pelo refresh-info.
        Útil quando o refresh-info falha mas ainda queremos os participantes.
        """
        try:
            logger.info(f"🔍 [PARTICIPANTS] Iniciando busca direta de participantes")
            logger.info(f"   Conversation ID: {conversation.id}")
            logger.info(f"   Conversation Type: {conversation.conversation_type}")
            logger.info(f"   Contact Phone: {conversation.contact_phone}")
            logger.info(f"   Instance Name: {conversation.instance_name}")
            
            # ✅ CORREÇÃO: Buscar instância WhatsApp e EvolutionConnection separadamente (como no refresh-info)
            from apps.notifications.models import WhatsAppInstance
            from apps.connections.models import EvolutionConnection
            
            wa_instance = WhatsAppInstance.objects.filter(
                tenant=conversation.tenant,
                instance_name=conversation.instance_name
            ).first()
            
            if not wa_instance:
                logger.warning(f"⚠️ [PARTICIPANTS] Instância não encontrada: {conversation.instance_name}")
                logger.warning(f"   Tentando buscar por friendly_name...")
                # Tentar buscar por friendly_name também
                wa_instance = WhatsAppInstance.objects.filter(
                    tenant=conversation.tenant,
                    friendly_name=conversation.instance_name
                ).first()
                
                if not wa_instance:
                    logger.error(f"❌ [PARTICIPANTS] Instância não encontrada nem por instance_name nem por friendly_name")
                    return []
                else:
                    logger.info(f"✅ [PARTICIPANTS] Instância encontrada por friendly_name: {wa_instance.instance_name}")
            
            # ✅ CORREÇÃO: Buscar EvolutionConnection separadamente (não tem atributo connection)
            evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
            if not evolution_server:
                logger.error(f"❌ [PARTICIPANTS] Nenhum servidor Evolution configurado!")
                return []
            
            # Usar mesma lógica do refresh-info
            base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
            api_key = wa_instance.api_key or evolution_server.api_key
            instance_name = wa_instance.instance_name  # UUID da instância
            
            logger.info(f"✅ [PARTICIPANTS] Configuração encontrada:")
            logger.info(f"   Base URL: {base_url}")
            logger.info(f"   Instance Name: {instance_name}")
            logger.info(f"   API Key: {'***' if api_key else 'NÃO ENCONTRADA'}")
            
            # Obter group_jid do metadata ou contact_phone
            conversation.refresh_from_db()  # ✅ IMPORTANTE: Recarregar do banco
            group_metadata = conversation.group_metadata or {}
            group_jid = group_metadata.get('group_id')
            
            # ✅ VALIDAÇÃO CRÍTICA: Se group_id não existe ou termina com @lid, tentar buscar de mensagens recentes
            # ✅ CORREÇÃO: Não verificar comprimento - grupos podem ter IDs longos e ainda assim serem válidos
            if not group_jid or group_jid.endswith('@lid'):
                logger.warning(f"⚠️ [PARTICIPANTS] group_id não encontrado ou é LID, tentando buscar de mensagens recentes...")
                # Buscar mensagem recente do grupo para extrair remoteJid real
                from apps.chat.models import Message
                recent_message = Message.objects.filter(
                    conversation=conversation,
                    direction='incoming'
                ).order_by('-created_at').first()
                
                if recent_message and recent_message.metadata:
                    # Tentar extrair remoteJid do metadata da mensagem
                    message_metadata = recent_message.metadata or {}
                    remote_jid = message_metadata.get('remoteJid') or message_metadata.get('remote_jid')
                    remote_jid_alt = message_metadata.get('remoteJidAlt') or message_metadata.get('remote_jid_alt')
                    
                    # ✅ CORREÇÃO: Se grupo usa LID, remoteJid pode ser telefone individual
                    # Tentar usar remoteJid convertido para @g.us
                    if remote_jid and '@s.whatsapp.net' in remote_jid:
                        # Converter telefone individual para @g.us
                        phone_part = remote_jid.split('@')[0]
                        group_jid = f"{phone_part}@g.us"
                        logger.info(f"✅ [PARTICIPANTS] group_jid construído a partir de remoteJid: {group_jid}")
                        # Salvar no group_metadata para próxima vez
                        conversation.group_metadata = {
                            **group_metadata,
                            'group_id': group_jid,
                            'group_id_lid': remote_jid_alt if remote_jid_alt and remote_jid_alt.endswith('@lid') else None,
                            'uses_lid': bool(remote_jid_alt and remote_jid_alt.endswith('@lid'))
                        }
                        conversation.save(update_fields=['group_metadata'])
                    elif remote_jid and '@g.us' in remote_jid:
                        group_jid = remote_jid
                        logger.info(f"✅ [PARTICIPANTS] group_jid encontrado em mensagem recente: {group_jid}")
                        # Salvar no group_metadata para próxima vez
                        conversation.group_metadata = {
                            **group_metadata,
                            'group_id': group_jid
                        }
                        conversation.save(update_fields=['group_metadata'])
                    else:
                        logger.warning(f"⚠️ [PARTICIPANTS] Não foi possível extrair group_jid de mensagens recentes")
            
            if not group_jid:
                # ✅ CORREÇÃO: Usar mesma lógica do refresh-info para construir group_jid
                raw_phone = conversation.contact_phone
                if not raw_phone:
                    logger.warning(f"⚠️ [PARTICIPANTS] Não foi possível determinar group_jid (contact_phone vazio)")
                    return []
                
                # ✅ VALIDAÇÃO CRÍTICA: Se contact_phone termina com @lid, não usar (grupo usa LID)
                # ✅ CORREÇÃO: @g.us = grupo válido, não é LID. Apenas @lid é LID.
                if raw_phone.endswith('@lid'):
                    logger.error(f"❌ [PARTICIPANTS] contact_phone é LID: {raw_phone}, não é possível buscar participantes")
                    # ✅ CORREÇÃO: Se grupo usa LID, retornar participantes do group_metadata (se existirem)
                    if group_metadata and group_metadata.get('uses_lid'):
                        participants_from_metadata = group_metadata.get('participants', [])
                        if participants_from_metadata:
                            logger.info(f"✅ [PARTICIPANTS] Grupo usa LID, retornando {len(participants_from_metadata)} participantes do metadata")
                            cleaned_participants = clean_participants_for_metadata(participants_from_metadata)
                            return cleaned_participants
                    return []
                
                # ✅ VALIDAÇÃO: Se group_metadata indica que grupo usa LID, não tentar buscar via API
                if group_metadata and group_metadata.get('uses_lid'):
                    logger.warning(f"⚠️ [PARTICIPANTS] Grupo usa LID, não é possível buscar via API")
                    # Retornar participantes do metadata se existirem
                    participants_from_metadata = group_metadata.get('participants', [])
                    if participants_from_metadata:
                        logger.info(f"✅ [PARTICIPANTS] Retornando {len(participants_from_metadata)} participantes do metadata")
                        cleaned_participants = clean_participants_for_metadata(participants_from_metadata)
                        return cleaned_participants
                    return []
                
                # ✅ USAR JID COMPLETO - Evolution API aceita:
                # - Grupos: xxx@g.us
                # ⚠️ IMPORTANTE: @lid é formato de participante, NÃO de grupo!
                if '@g.us' in raw_phone:
                    # Já tem @g.us, usar como está
                    group_jid = raw_phone
                    logger.info(f"✅ [PARTICIPANTS] group_jid já tem @g.us: {group_jid}")
                elif '@s.whatsapp.net' in raw_phone:
                    # Formato errado (individual), corrigir para grupo
                    group_jid = raw_phone.replace('@s.whatsapp.net', '@g.us')
                    logger.info(f"🔄 [PARTICIPANTS] Corrigindo formato individual para grupo: {group_jid}")
                else:
                    # Adicionar @g.us se não tiver (padrão para grupos)
                    clean_id = raw_phone.replace('+', '').strip()
                    group_jid = f"{clean_id}@g.us"
                    logger.info(f"➕ [PARTICIPANTS] Adicionando @g.us: {group_jid}")
            
            logger.info(f"🔄 [PARTICIPANTS] group_jid final: {group_jid}")
            logger.info(f"   Raw contact_phone: {conversation.contact_phone}")
            
            # ✅ VALIDAÇÃO FINAL: Se group_jid termina com @lid, não tentar buscar (grupo usa LID)
            # ✅ CORREÇÃO CRÍTICA: @g.us = grupo válido, NÃO é LID. Apenas @lid é LID.
            # IDs de grupo podem ser longos (ex: 120363404279692186@g.us) e ainda assim são válidos!
            if group_jid.endswith('@lid'):
                logger.error(f"❌ [PARTICIPANTS] group_jid é LID: {group_jid}, não é possível buscar participantes")
                # ✅ CORREÇÃO: Se grupo usa LID, retornar participantes do group_metadata (se existirem)
                if group_metadata and group_metadata.get('uses_lid'):
                    participants_from_metadata = group_metadata.get('participants', [])
                    if participants_from_metadata:
                        logger.info(f"✅ [PARTICIPANTS] Grupo usa LID, retornando {len(participants_from_metadata)} participantes do metadata")
                        cleaned_participants = clean_participants_for_metadata(participants_from_metadata)
                        return cleaned_participants
                return []
            
            # ✅ VALIDAÇÃO: Se group_jid termina com @g.us, é grupo válido e pode ser buscado
            # Não verificar comprimento do ID - grupos podem ter IDs longos e ainda assim serem válidos
            if not group_jid.endswith('@g.us'):
                logger.warning(f"⚠️ [PARTICIPANTS] group_jid não termina com @g.us: {group_jid}")
                # Tentar usar mesmo assim se não for @lid
                if group_jid.endswith('@lid'):
                    logger.error(f"❌ [PARTICIPANTS] group_jid é LID: {group_jid}, não é possível buscar participantes")
                    return []
            
            logger.info(f"🔄 [PARTICIPANTS] Buscando participantes diretamente: {group_jid}")
            
            import httpx
            headers = {'apikey': api_key}
            
            with httpx.Client(timeout=15.0) as client:
                # ✅ MELHORIA: Tentar primeiro find-group-by-jid (retorna grupo completo com participantes)
                # Referência: https://www.postman.com/agenciadgcode/evolution-api/request/smqme9o/find-group-by-jid
                logger.info(f"🔄 [PARTICIPANTS] Tentando find-group-by-jid primeiro...")
                find_group_endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                logger.info(f"   Endpoint: {find_group_endpoint}")
                logger.info(f"   Params: groupJid={group_jid}")
                
                find_group_response = client.get(
                    find_group_endpoint,
                    params={'groupJid': group_jid},
                    headers=headers
                )
                
                if find_group_response.status_code == 200:
                    group_data = find_group_response.json()
                    logger.info(f"✅ [PARTICIPANTS] find-group-by-jid retornou dados do grupo")
                    logger.info(f"   📋 [DEBUG] Estrutura completa do grupo: {group_data}")
                    
                    # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                    import json
                    logger.critical(f"📦 [PARTICIPANTS API] JSON COMPLETO retornado por find-group-by-jid:")
                    logger.critical(f"   {json.dumps(group_data, indent=2, ensure_ascii=False)}")
                    
                    # Extrair participantes do grupo
                    raw_participants = group_data.get('participants', [])
                    if raw_participants:
                        logger.info(f"✅ [PARTICIPANTS] {len(raw_participants)} participantes encontrados via find-group-by-jid")
                        logger.info(f"   📋 [DEBUG] Primeiro participante: {raw_participants[0] if raw_participants else 'N/A'}")
                        # Processar participantes (código abaixo)
                    else:
                        logger.warning(f"⚠️ [PARTICIPANTS] find-group-by-jid não retornou participantes, tentando com getParticipants=true...")
                        # ✅ NOVA TENTATIVA: Chamar novamente com getParticipants=true
                        try:
                            find_group_with_participants = client.get(
                                find_group_endpoint,
                                params={'groupJid': group_jid, 'getParticipants': 'true'},
                                headers=headers
                            )
                            if find_group_with_participants.status_code == 200:
                                group_data_with_participants = find_group_with_participants.json()
                                
                                # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                                import json
                                logger.critical(f"📦 [PARTICIPANTS API] JSON COMPLETO retornado por find-group-by-jid com getParticipants=true:")
                                logger.critical(f"   {json.dumps(group_data_with_participants, indent=2, ensure_ascii=False)}")
                                
                                raw_participants = group_data_with_participants.get('participants', [])
                                if raw_participants:
                                    logger.info(f"✅ [PARTICIPANTS] {len(raw_participants)} participantes encontrados via find-group-by-jid com getParticipants=true")
                                    logger.info(f"   📋 [DEBUG] Primeiro participante: {raw_participants[0] if raw_participants else 'N/A'}")
                                else:
                                    logger.warning(f"⚠️ [PARTICIPANTS] find-group-by-jid com getParticipants=true não retornou participantes")
                                    raw_participants = None
                            else:
                                logger.warning(f"⚠️ [PARTICIPANTS] find-group-by-jid com getParticipants=true retornou {find_group_with_participants.status_code}")
                                raw_participants = None
                        except Exception as e:
                            logger.warning(f"⚠️ [PARTICIPANTS] Erro ao buscar com getParticipants=true: {e}")
                            raw_participants = None
                else:
                    logger.warning(f"⚠️ [PARTICIPANTS] find-group-by-jid retornou {find_group_response.status_code}, tentando find-participants...")
                    raw_participants = None
                
                # ✅ FALLBACK: Se find-group-by-jid não funcionou, tentar /group/participants
                # Referência: https://evo.rbtec.com.br/group/participants/{instance}?groupJid={groupJid}
                # Retorna: {"participants": [{"id": "@lid", "phoneNumber": "@s.whatsapp.net", "admin": "...", "name": "", "imgUrl": "..."}]}
                if not raw_participants:
                    participants_endpoint = f"{base_url}/group/participants/{instance_name}"
                    logger.info(f"🔄 [PARTICIPANTS] Tentando endpoint /group/participants: {participants_endpoint}")
                    logger.info(f"   Params: groupJid={group_jid}")
                    
                    participants_response = client.get(
                        participants_endpoint,
                        params={'groupJid': group_jid},
                        headers=headers
                    )
                    
                    logger.info(f"📥 [PARTICIPANTS] Resposta status: {participants_response.status_code}")
                    
                    if participants_response.status_code == 200:
                        participants_data = participants_response.json()
                        logger.info(f"📥 [PARTICIPANTS] Dados recebidos: {type(participants_data)}")
                        
                        # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                        import json
                        logger.critical(f"📦 [PARTICIPANTS API] JSON COMPLETO retornado por /group/participants:")
                        logger.critical(f"   {json.dumps(participants_data, indent=2, ensure_ascii=False)}")
                        
                        # ✅ CORREÇÃO: A resposta é objeto com "participants" array
                        # Cada participante tem: id (@lid), phoneNumber (@s.whatsapp.net), admin, name, imgUrl
                        if isinstance(participants_data, dict):
                            raw_participants = participants_data.get('participants', [])
                        elif isinstance(participants_data, list):
                            raw_participants = participants_data
                        else:
                            raw_participants = []
                    else:
                        logger.error(f"❌ [PARTICIPANTS] /group/participants retornou {participants_response.status_code}")
                        raw_participants = []
                
                if raw_participants:
                    logger.info(f"📥 [PARTICIPANTS] Raw participants: {len(raw_participants)} encontrados")
                    
                    # ✅ CORREÇÃO CRÍTICA: Usar mesmo método de processamento de group_info
                    # Primeiro, coletar todos os telefones reais para busca em batch
                    all_phones = []
                    for participant in raw_participants:
                        participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number') or ''
                        if participant_phone_number:
                            phone_raw = participant_phone_number.split('@')[0]
                            if phone_raw and not is_lid_number(phone_raw):
                                all_phones.append(phone_raw)
                    
                    # Buscar contatos em batch usando telefones reais
                    contacts_map = {}
                    if all_phones:
                        from apps.contacts.models import Contact
                        from apps.contacts.signals import normalize_phone_for_search
                        from apps.notifications.services import normalize_phone
                        normalized_phones = []
                        for p in all_phones:
                            normalized = normalize_phone(p)
                            if normalized:
                                normalized_phones.append(normalized)
                                normalized_phones.append(normalize_phone_for_search(normalized))
                        
                        contacts = Contact.objects.filter(
                            tenant=conversation.tenant,
                            phone__in=normalized_phones + all_phones
                        ).values('phone', 'name')
                        
                        for contact in contacts:
                            normalized_contact_phone = normalize_phone_for_search(contact['phone'])
                            contacts_map[normalized_contact_phone] = contact.get('name', '')
                            # Também mapear telefone normalizado
                            phone_normalized = normalize_phone(contact['phone'])
                            if phone_normalized:
                                contacts_map[normalize_phone_for_search(phone_normalized)] = contact.get('name', '')
                    
                    # Processar cada participante usando phoneNumber (mesmo método de group_info)
                    participants_list = []
                    for participant in raw_participants:
                        participant_id = participant.get('id') or participant.get('jid') or ''
                        participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number') or ''
                        
                        logger.info(f"   🔍 [PARTICIPANTS] Processando participante: id={participant_id}, phoneNumber={participant_phone_number}")
                        
                        # ✅ PRIORIDADE: Usar phoneNumber (telefone real) primeiro
                        phone_raw = None
                        if participant_phone_number:
                            # Extrair telefone do phoneNumber (formato: 5517996196795@s.whatsapp.net)
                            phone_raw = participant_phone_number.split('@')[0]
                            logger.info(f"   ✅ [PARTICIPANTS] Telefone extraído de phoneNumber: {phone_raw}")
                        elif participant_id and not participant_id.endswith('@lid'):
                            # Fallback: usar id apenas se não for LID
                            if '@' in participant_id and participant_id.endswith('@s.whatsapp.net'):
                                phone_raw = participant_id.split('@')[0]
                                logger.info(f"   ✅ [PARTICIPANTS] Telefone extraído de id: {phone_raw}")
                        
                        # Se não encontrou telefone válido, pular
                        if not phone_raw:
                            logger.warning(f"   ⚠️ [PARTICIPANTS] Participante sem phoneNumber válido: id={participant_id}")
                            continue
                        
                        # Normalizar telefone para E.164
                        from apps.notifications.services import normalize_phone
                        normalized_phone = normalize_phone(phone_raw)
                        if not normalized_phone:
                            normalized_phone = phone_raw
                        
                        # Buscar nome do contato usando telefone real
                        from apps.contacts.signals import normalize_phone_for_search
                        normalized_phone_for_search = normalize_phone_for_search(normalized_phone)
                        contact_name = contacts_map.get(normalized_phone_for_search) or contacts_map.get(normalized_phone) or contacts_map.get(phone_raw)
                        
                        # ✅ CORREÇÃO: Prioridade: nome do contato > pushname da Evolution API > telefone formatado
                        participant_name = ''
                        if contact_name:
                            participant_name = contact_name
                            logger.info(f"   ✅ [PARTICIPANTS] Nome do contato encontrado: {participant_name}")
                        else:
                            # Se não encontrou contato cadastrado, buscar pushname da Evolution API
                            logger.info(f"   🔍 [PARTICIPANTS] Contato não encontrado, buscando pushname na Evolution API...")
                            pushname = fetch_pushname_from_evolution(wa_instance, normalized_phone)
                            if pushname:
                                participant_name = pushname
                                logger.info(f"   ✅ [PARTICIPANTS] Pushname encontrado via Evolution API: {participant_name}")
                            else:
                                logger.info(f"   ℹ️ [PARTICIPANTS] Pushname não encontrado, name vazio (telefone será mostrado)")
                        
                        contact = Contact.objects.filter(
                            tenant=conversation.tenant,
                            phone__in=[normalized_phone_for_search, normalized_phone, phone_raw, f"+{phone_raw}"]
                        ).first()
                        
                        # ✅ CORREÇÃO: Extrair pushname da resposta da API
                        # A API pode retornar: name, pushName, notify, ou não ter nada
                        # ⚠️ CRÍTICO: Validar se não é LID antes de usar
                        logger.info(f"🔍 [PARTICIPANTS] Processando participante: id={participant_id}, phoneNumber={participant_phone_number}")
                        raw_pushname = (
                            participant.get('pushName') or 
                            participant.get('name') or 
                            participant.get('notify') or 
                            ''
                        )
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Se pushname é LID ou igual ao participant_id (LID), não usar
                        pushname = ''
                        if raw_pushname:
                            # Verificar se não é LID
                            if not is_lid_number(raw_pushname) and raw_pushname != participant_id:
                                # Verificar se não é igual ao LID (sem @lid)
                                if not (participant_id.endswith('@lid') and raw_pushname == participant_id.replace('@lid', '')):
                                    pushname = raw_pushname
                                    logger.info(f"   ✅ Pushname válido extraído: {pushname}")
                                else:
                                    logger.warning(f"   ⚠️ Pushname é igual ao LID (sem @lid), ignorando: {raw_pushname}")
                            else:
                                logger.warning(f"   ⚠️ Pushname é LID ou inválido, ignorando: {raw_pushname}")
                        
                        logger.info(f"   Pushname final: {pushname if pushname else '(vazio - não é LID)'}")
                        
                        # ✅ CORREÇÃO: Prioridade: pushname válido > nome do contato
                        # NÃO usar telefone como name - deixar vazio para frontend mostrar apenas telefone formatado
                        display_name = pushname
                        if not display_name and contact:
                            display_name = contact.name
                            logger.info(f"   Usando nome do contato: {display_name}")
                        # ✅ CORREÇÃO: Se não tem pushname nem contato, deixar name vazio
                        # O frontend vai mostrar apenas o telefone formatado na linha de baixo
                        if not display_name:
                            display_name = ''  # Vazio - frontend mostrará apenas telefone formatado
                            logger.info(f"   Sem pushname nem contato - name vazio (telefone será mostrado separadamente)")
                        
                        # ✅ CORREÇÃO CRÍTICA: Garantir que phone sempre tenha telefone real
                        # Se normalized_phone veio de phoneNumber, usar ele
                        # Se não, tentar extrair de phoneNumber novamente
                        final_phone = normalized_phone
                        if participant_phone_number:
                            # Extrair telefone do phoneNumber (JID real)
                            phone_from_number = participant_phone_number.split('@')[0] if '@' in participant_phone_number else participant_phone_number
                            normalized_from_number = normalize_phone(phone_from_number)
                            if normalized_from_number:
                                final_phone = normalized_from_number
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Se final_phone ainda é LID, tentar usar phoneNumber novamente
                        if is_lid_number(final_phone):
                            logger.warning(f"   ⚠️ [PARTICIPANTS] final_phone é LID: {final_phone}, tentando usar phoneNumber...")
                            if participant_phone_number:
                                phone_from_number = participant_phone_number.split('@')[0] if '@' in participant_phone_number else participant_phone_number
                                normalized_from_number = normalize_phone(phone_from_number)
                                if normalized_from_number and not is_lid_number(normalized_from_number):
                                    final_phone = normalized_from_number
                                    logger.info(f"   ✅ [PARTICIPANTS] Telefone real obtido de phoneNumber: {final_phone}")
                                else:
                                    logger.warning(f"   ⚠️ [PARTICIPANTS] Não foi possível obter telefone real, deixando vazio")
                                    final_phone = ''  # Não salvar LID como telefone
                            else:
                                logger.warning(f"   ⚠️ [PARTICIPANTS] Sem phoneNumber, não é possível obter telefone real")
                                final_phone = ''  # Não salvar LID como telefone
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Se display_name é LID, deixar vazio
                        if display_name and is_lid_number(display_name):
                            logger.warning(f"   ⚠️ [PARTICIPANTS] display_name é LID: {display_name}, deixando vazio")
                            display_name = ''
                        
                        # ✅ CORREÇÃO: Garantir que phoneNumber seja salvo (pode vir de diferentes campos)
                        saved_phone_number = participant_phone_number
                        if not saved_phone_number and phone_raw and not is_lid_number(phone_raw):
                            # Se não tem phoneNumber mas tem phone_raw válido, construir JID
                            saved_phone_number = f"{phone_raw}@s.whatsapp.net"
                        
                        # ✅ VALIDAÇÃO FINAL: Se não temos telefone real nem phoneNumber, não salvar o participante
                        if not final_phone and not saved_phone_number:
                            logger.warning(f"⚠️ [PARTICIPANTS] Participante sem telefone real nem phoneNumber, pulando: jid={participant_id}")
                            continue
                        
                        participant_info = {
                            'phone': final_phone,  # Telefone real normalizado E.164 (NUNCA LID)
                            'name': display_name,  # Nome para exibição (pushname > contato) - NUNCA LID
                            'pushname': pushname,  # Pushname original da API (pode ser vazio se era LID)
                            'jid': participant_id,  # LID ou JID original
                            'phoneNumber': saved_phone_number  # JID real do telefone (@s.whatsapp.net)
                        }
                        logger.info(f"   ✅ [PARTICIPANTS] Participante final: phone={final_phone}, phoneNumber={saved_phone_number}, jid={participant_id}")
                        logger.info(f"   ✅ Participante processado: {participant_info}")
                        participants_list.append(participant_info)
                    
                    logger.info(f"✅ [PARTICIPANTS] {len(participants_list)} participantes processados")
                    
                    # ✅ BONUS: Atualizar group_metadata com os participantes encontrados
                    if participants_list:
                        # ✅ CRÍTICO: Limpar participantes antes de salvar (remover LIDs do phone)
                        cleaned_participants = clean_participants_for_metadata(participants_list)
                        conversation.group_metadata = {
                            **group_metadata,
                            'participants': cleaned_participants
                        }
                        conversation.save(update_fields=['group_metadata'])
                        logger.info(f"💾 [PARTICIPANTS] Metadata atualizado com participantes")
                        
                        # ✅ MELHORIA: Invalidar cache de participantes
                        from django.core.cache import cache
                        cache_key = f"group_participants:{conversation.id}"
                        cache.delete(cache_key)
                        logger.info(f"🗑️ [PARTICIPANTS] Cache invalidado para conversa {conversation.id}")
                    
                    return participants_list
                elif participants_response.status_code == 404:
                    # ✅ TENTATIVA 2: Tentar findGroupInfos com getParticipants=true (fallback)
                    logger.warning(f"⚠️ [PARTICIPANTS] getParticipants retornou 404, tentando findGroupInfos com getParticipants=true...")
                    try:
                        alt_endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                        logger.info(f"🔄 [PARTICIPANTS] Tentando endpoint alternativo: {alt_endpoint}")
                        alt_response = client.get(
                            alt_endpoint,
                            params={'groupJid': group_jid, 'getParticipants': 'true'},
                            headers=headers
                        )
                        
                        if alt_response.status_code == 200:
                            alt_data = alt_response.json()
                            
                            # ✅ LOG CRÍTICO: Mostrar JSON completo retornado
                            import json
                            logger.critical(f"📦 [PARTICIPANTS API] JSON COMPLETO retornado por findGroupInfos com getParticipants=true (alternativo):")
                            logger.critical(f"   {json.dumps(alt_data, indent=2, ensure_ascii=False)}")
                            
                            raw_participants = alt_data.get('participants', [])
                            logger.info(f"✅ [PARTICIPANTS] Endpoint alternativo retornou {len(raw_participants)} participantes")
                            
                            # ✅ CORREÇÃO: Processar da mesma forma com normalização e pushname
                            participants_list = []
                            from apps.contacts.models import Contact
                            from apps.contacts.signals import normalize_phone_for_search
                            from apps.notifications.services import normalize_phone
                            
                            for participant in raw_participants:
                                participant_id = participant.get('id') or participant.get('jid') or ''
                                if participant_id:
                                    phone_raw = participant_id.split('@')[0]
                                    
                                    # Normalizar telefone para E.164
                                    normalized_phone = normalize_phone(phone_raw)
                                    if not normalized_phone:
                                        normalized_phone = phone_raw
                                    
                                    # Buscar contato
                                    normalized_phone_for_search = normalize_phone_for_search(normalized_phone)
                                    contact = Contact.objects.filter(
                                        tenant=conversation.tenant,
                                        phone__in=[normalized_phone_for_search, normalized_phone, phone_raw, f"+{phone_raw}"]
                                    ).first()
                                    
                                    # ✅ CORREÇÃO: Extrair pushname da resposta da API
                                    # ⚠️ CRÍTICO: Validar se não é LID antes de usar
                                    raw_pushname = (
                                        participant.get('pushName') or 
                                        participant.get('name') or 
                                        participant.get('notify') or 
                                        ''
                                    )
                                    
                                    # ✅ VALIDAÇÃO CRÍTICA: Se pushname é LID ou igual ao participant_id (LID), não usar
                                    pushname = ''
                                    if raw_pushname:
                                        # Verificar se não é LID
                                        if not is_lid_number(raw_pushname) and raw_pushname != participant_id:
                                            # Verificar se não é igual ao LID (sem @lid)
                                            if not (participant_id.endswith('@lid') and raw_pushname == participant_id.replace('@lid', '')):
                                                pushname = raw_pushname
                                    
                                    # ✅ CORREÇÃO: Prioridade: pushname válido > nome do contato
                                    # NÃO usar telefone como name - deixar vazio para frontend mostrar apenas telefone formatado
                                    display_name = pushname
                                    if not display_name and contact:
                                        display_name = contact.name
                                    # ✅ CORREÇÃO: Se não tem pushname nem contato, deixar name vazio
                                    # O frontend vai mostrar apenas o telefone formatado na linha de baixo
                                    if not display_name:
                                        display_name = ''  # Vazio - frontend mostrará apenas telefone formatado
                                    
                                    participant_info = {
                                        'phone': normalized_phone,
                                        'name': display_name,
                                        'pushname': pushname,
                                        'jid': participant_id
                                    }
                                    participants_list.append(participant_info)
                            
                            if participants_list:
                                # ✅ CRÍTICO: Limpar participantes antes de salvar (remover LIDs do phone)
                                cleaned_participants = clean_participants_for_metadata(participants_list)
                                conversation.group_metadata = {
                                    **group_metadata,
                                    'participants': cleaned_participants
                                }
                                conversation.save(update_fields=['group_metadata'])
                                
                                # ✅ MELHORIA: Invalidar cache de participantes
                                from django.core.cache import cache
                                cache_key = f"group_participants:{conversation.id}"
                                cache.delete(cache_key)
                                logger.info(f"🗑️ [PARTICIPANTS] Cache invalidado para conversa {conversation.id}")
                            
                            return participants_list
                    except Exception as e:
                        logger.warning(f"⚠️ [PARTICIPANTS] Erro no endpoint alternativo: {e}")
                
                logger.warning(f"⚠️ [PARTICIPANTS] API retornou {participants_response.status_code}")
                logger.warning(f"   Response body: {participants_response.text[:200]}")
                return []
                    
        except httpx.TimeoutException:
            logger.error(f"⏱️ [PARTICIPANTS] Timeout ao buscar participantes da Evolution API")
            return []
        except httpx.RequestError as e:
            logger.error(f"❌ [PARTICIPANTS] Erro de conexão ao buscar participantes: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ [PARTICIPANTS] Erro inesperado ao buscar participantes diretamente: {e}", exc_info=True)
            return []
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """
        Atribui conversa a um usuário.
        Body: { "user_id": "uuid" }
        """
        conversation = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verifica se o usuário pertence ao mesmo tenant e departamento
        from apps.authn.models import User
        try:
            user = User.objects.get(
                id=user_id,
                tenant=conversation.tenant,
                departments=conversation.department
            )
            conversation.assigned_to = user
            conversation.save(update_fields=['assigned_to'])
            
            return Response(
                ConversationSerializer(conversation).data,
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuário não encontrado ou não pertence ao departamento'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        Fecha uma conversa.
        
        ✅ CORREÇÃO CRÍTICA: Remove departamento ao fechar para que quando
        uma nova mensagem chegar, a conversa volte para o Inbox (sem departamento).
        """
        conversation = self.get_object()
        conversation.status = 'closed'
        conversation.department = None  # ✅ Remover departamento para voltar ao Inbox quando reabrir
        conversation.save(update_fields=['status', 'department'])
        
        logger.info(f"🔒 [CONVERSA] Conversa {conversation.id} fechada e departamento removido (volta ao Inbox quando reabrir)")
        
        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def debug_list_groups(self, request):
        """
        🔧 DEBUG: Lista todos os grupos da instância Evolution.
        
        Útil para comparar JIDs reais vs JIDs salvos no banco.
        """
        import logging
        import httpx
        from apps.connections.models import EvolutionConnection
        
        logger = logging.getLogger(__name__)
        
        # Buscar instância WhatsApp ativa
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            return Response(
                {'error': 'Nenhuma instância WhatsApp ativa encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            return Response(
                {'error': 'Servidor Evolution não configurado'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        try:
            base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
            api_key = wa_instance.api_key or evolution_server.api_key
            instance_name = wa_instance.instance_name
            
            headers = {
                'apikey': api_key,
                'Content-Type': 'application/json'
            }
            
            # Endpoint: /group/fetchAllGroups/{instance}
            # REQUER query param: getParticipants (true ou false)
            endpoint = f"{base_url}/group/fetchAllGroups/{instance_name}"
            params = {'getParticipants': 'false'}  # Obrigatório! Não precisamos dos participantes detalhados
            
            logger.info(f"🔍 [DEBUG] Listando todos os grupos da instância {instance_name}")
            logger.info(f"   URL: {endpoint}")
            logger.info(f"   Params: {params}")
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(endpoint, headers=headers, params=params)
                
                if response.status_code == 200:
                    groups = response.json()
                    
                    logger.info(f"✅ [DEBUG] {len(groups)} grupos encontrados")
                    
                    # Formatar resposta para debug
                    debug_data = []
                    for group in groups:
                        debug_data.append({
                            'id': group.get('id'),
                            'subject': group.get('subject'),
                            'participants_count': len(group.get('participants', [])),
                            'owner': group.get('owner'),
                            'creation': group.get('creation'),
                        })
                    
                    return Response({
                        'instance': instance_name,
                        'total_groups': len(groups),
                        'groups': debug_data,
                        'raw_response': groups  # Resposta completa para análise
                    })
                else:
                    logger.error(f"❌ [DEBUG] Erro ao listar grupos: {response.status_code}")
                    logger.error(f"   Response: {response.text[:500]}")
                    return Response(
                        {'error': f'Erro ao listar grupos: {response.status_code}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            logger.exception(f"❌ [DEBUG] Exceção ao listar grupos")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        """Reabre uma conversa."""
        conversation = self.get_object()
        conversation.status = 'open'
        conversation.save(update_fields=['status'])
        
        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """
        Marca todas as mensagens recebidas (não enviadas por nós) como lidas.
        Envia confirmação de leitura para Evolution API.
        
        ✅ CORREÇÕES:
        - Verifica connection_state antes de enviar read receipt
        - Trata erros adequadamente (não trava se uma mensagem falhar)
        - Timeout adequado para evitar travamento
        - Processa mensagens de forma eficiente
        """
        from apps.chat.tasks import enqueue_mark_as_read
        from django.db import transaction
        
        conversation = self.get_object()
        
        # Buscar mensagens recebidas (direction='incoming') que ainda não foram marcadas como lidas
        unread_qs = Message.objects.filter(
            conversation=conversation,
            direction='incoming',
            status__in=['sent', 'delivered']  # Ainda não lidas
        ).select_related('conversation').order_by('-created_at')
        
        # ✅ CORREÇÃO: Processar TODAS as mensagens não lidas de uma vez
        # O processamento é assíncrono via Redis Streams, então não há risco de timeout
        # Limite máximo de segurança: 1000 mensagens (caso extremo)
        max_messages_per_request = int(os.getenv('CHAT_MARK_AS_READ_MAX_MESSAGES', '1000'))
        unread_messages = list(unread_qs[:max_messages_per_request])
        
        if not unread_messages:
            return Response(
                {
                    'success': True,
                    'marked_count': 0,
                    'failed_count': 0,
                    'skipped_count': 0,
                    'message': 'Nenhuma mensagem pendente para marcar como lida',
                    'queued': 0
                },
                status=status.HTTP_200_OK
            )
        
        message_ids = [msg.id for msg in unread_messages]
        messages_with_receipt = [msg for msg in unread_messages if msg.message_id]
        skipped_count = len(unread_messages) - len(messages_with_receipt)
        failed_count = 0
        
        with transaction.atomic():
            Message.objects.filter(id__in=message_ids).update(status='seen')
        
        marked_count = len(message_ids)
        queued = 0
        
        for msg in messages_with_receipt:
            try:
                enqueue_mark_as_read(str(conversation.id), str(msg.id))
                queued += 1
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"❌ [MARK AS READ] Erro ao enfileirar read receipt para mensagem {msg.id}: {e}",
                    exc_info=True
                )
        
        # ✅ CORREÇÃO: Broadcast conversation_updated para atualizar lista em tempo real
        # ✅ FIX: Sempre fazer broadcast, mesmo se marked_count = 0 (para atualizar unread_count)
        from apps.chat.utils.websocket import broadcast_conversation_updated
        from apps.chat.api.serializers import ConversationSerializer
        
        # ✅ FIX CRÍTICO: Recarregar conversa do banco para garantir unread_count atualizado
        conversation.refresh_from_db()
        
        # Serializar conversa atualizada (com unread_count=0)
        serializer = ConversationSerializer(conversation, context={'request': request})
        conversation_data = serializer.data
        
        # ✅ FIX: Passar request para broadcast_conversation_updated para garantir contexto correto
        # Broadcast para todo o tenant (atualiza lista de conversas)
        broadcast_conversation_updated(conversation, request=request)
        
        # ✅ FIX: Também enviar para o grupo específico da conversa
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.utils.serialization import serialize_conversation_for_ws
        
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        tenant_group = f"chat_tenant_{conversation.tenant_id}"
        
        conv_data_serializable = serialize_conversation_for_ws(conversation)
        
        # Broadcast para a sala da conversa (atualiza chat aberto)
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'conversation_updated',
                'conversation': conv_data_serializable
            }
        )
        
        # Broadcast para todo o tenant (atualiza lista de conversas)
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {
                'type': 'conversation_updated',
                'conversation': conv_data_serializable
            }
        )
        
        logger.info(
            f"📡 [WEBSOCKET] {marked_count} mensagens marcadas como lidas "
            f"(falhas enqueue: {failed_count}, sem message_id: {skipped_count}, enfileiradas: {queued}), broadcast enviado para tenant"
        )
        
        return Response(
            {
                'success': True,
                'marked_count': marked_count,
                'failed_count': failed_count,
                'skipped_count': skipped_count,
                'queued': queued,
                'message': f'{marked_count} mensagens marcadas como lidas (read receipt assíncrono)',
                'conversation': conversation_data  # ✅ FIX: Retornar conversa atualizada
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'], url_path='upload-media')
    def upload_media(self, request):
        """Endpoint legado desativado. Use o fluxo com presigned URL.
        """
        return Response(
            {
                'error': 'Endpoint de upload multipart desativado. Use /messages/upload-presigned-url e /messages/confirm-upload.'
            },
            status=status.HTTP_410_GONE
        )
    
    @action(detail=False, methods=['post'], url_path='get-upload-url')
    def get_upload_url(self, request):
        """
        Gera URL pré-assinada para upload direto ao S3.
        
        Body:
            filename: Nome do arquivo
            content_type: MIME type
        
        Returns:
            {
                'upload_url': 'https://...',
                'file_key': 'chat_images/tenant/...',
                'expires_in': 3600
            }
        """
        from apps.chat.utils.s3 import get_s3_manager, generate_media_path
        
        filename = request.data.get('filename')
        content_type = request.data.get('content_type', 'application/octet-stream')
        
        if not filename:
            return Response(
                {'error': 'Filename é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Detectar tipo de mídia
        if content_type.startswith('image/'):
            media_type = 'image'
        elif content_type.startswith('audio/'):
            media_type = 'audio'
        elif content_type.startswith('video/'):
            media_type = 'video'
        else:
            media_type = 'document'
        
        # Gerar path no S3
        file_key = generate_media_path(
            str(request.user.tenant_id),
            f'chat_{media_type}s',
            filename
        )
        
        # Gerar URL presigned
        s3_manager = get_s3_manager()
        upload_url = s3_manager.generate_presigned_url(file_key, expiration=3600)
        
        if not upload_url:
            return Response(
                {'error': 'Erro ao gerar URL de upload'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'upload_url': upload_url,
            'file_key': file_key,
            'expires_in': 3600
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get', 'options'], url_path='profile-pic-proxy')
    def profile_pic_proxy(self, request):
        """
        Proxy para fotos de perfil do WhatsApp com cache Redis.
        Endpoint público (sem autenticação) para permitir carregamento em <img> tags.
        
        Query params:
        - url: URL da foto de perfil
        """
        import httpx
        from django.http import HttpResponse
        from django.core.cache import cache
        import logging
        import hashlib
        
        logger = logging.getLogger(__name__)
        
        # ✅ CORS Preflight: Responder OPTIONS com headers CORS
        if request.method == 'OPTIONS':
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            response['Access-Control-Max-Age'] = '86400'  # 24 horas
            return response
        
        profile_url = request.query_params.get('url')
        
        if not profile_url:
            logger.warning('🖼️ [PROXY] URL não fornecida')
            return Response(
                {'error': 'URL é obrigatória'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Gerar chave Redis baseada na URL
        cache_key = f"profile_pic:{hashlib.md5(profile_url.encode()).hexdigest()}"
        
        # Tentar buscar do cache Redis
        cached_data = cache.get(cache_key)
        
        if cached_data:
            logger.info(f'✅ [PROXY CACHE] Imagem servida do Redis: {profile_url[:80]}...')
            
            http_response = HttpResponse(
                cached_data['content'],
                content_type=cached_data['content_type']
            )
            http_response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
            http_response['Access-Control-Allow-Origin'] = '*'
            http_response['X-Cache'] = 'HIT'
            
            return http_response
        
        # Não está no cache, buscar do WhatsApp
        logger.info(f'🔄 [PROXY] Baixando imagem do WhatsApp: {profile_url[:80]}...')
        
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(profile_url)
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', 'image/jpeg')
                content = response.content
                
                logger.info(f'✅ [PROXY] Imagem baixada! Content-Type: {content_type} | Size: {len(content)} bytes')
                
                # Cachear no Redis por 7 dias
                cache.set(
                    cache_key,
                    {
                        'content': content,
                        'content_type': content_type
                    },
                    timeout=604800  # 7 dias
                )
                
                logger.info(f'💾 [PROXY] Imagem cacheada no Redis com chave: {cache_key}')
                
                # Retornar imagem
                http_response = HttpResponse(
                    content,
                    content_type=content_type
                )
                http_response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
                http_response['Access-Control-Allow-Origin'] = '*'
                http_response['X-Cache'] = 'MISS'
                
                return http_response
        
        except httpx.HTTPStatusError as e:
            logger.error(f'❌ [PROXY] Erro HTTP {e.response.status_code}: {profile_url[:80]}...')
            return Response(
                {'error': f'Erro ao buscar imagem: {e.response.status_code}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.error(f'❌ [PROXY] Erro: {str(e)} | URL: {profile_url[:80]}...', exc_info=True)
            return Response(
                {'error': f'Erro ao buscar imagem: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def my_conversations(self, request):
        """Lista conversas atribuídas ao usuário logado."""
        conversations = self.filter_queryset(
            self.get_queryset().filter(assigned_to=request.user)
        )
        
        page = self.paginate_queryset(conversations)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """
        Lista mensagens de uma conversa específica (paginado).
        GET /conversations/{id}/messages/?limit=50&offset=0
        
        ✅ PERFORMANCE: Paginação implementada para melhor performance
        ✅ CORREÇÃO: Tratamento explícito quando conversa não existe
        """
        try:
            conversation = self.get_object()
            
            # ✅ SEGURANÇA CRÍTICA: Verificar se conversa pertence ao tenant do usuário
            if conversation.tenant_id != request.user.tenant_id:
                logger.error(
                    f"🚨 [SEGURANÇA] Tentativa de acesso a conversa de outro tenant! "
                    f"Usuário: {request.user.email} (tenant: {request.user.tenant_id}), "
                    f"Conversa: {pk} (tenant: {conversation.tenant_id})"
                )
                return Response({
                    'error': 'Conversa não encontrada'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Conversation.DoesNotExist:
            # ✅ CORREÇÃO: Verificar se conversa existe mas não está acessível (problema de filtro/permissão)
            try:
                # Tentar buscar diretamente COM filtro de tenant para ver se existe
                direct_conversation = Conversation.objects.get(id=pk, tenant=request.user.tenant)
                logger.warning(
                    f"⚠️ [MESSAGES] Conversa {pk} existe mas não está acessível para usuário {request.user.id} "
                    f"(role: {request.user.role}, department: {direct_conversation.department_id}, "
                    f"status: {direct_conversation.status})"
                )
                return Response({
                    'results': [],
                    'count': 0,
                    'limit': int(request.query_params.get('limit', 15)),
                    'offset': int(request.query_params.get('offset', 0)),
                    'has_more': False,
                    'next': None,
                    'previous': None,
                    'error': 'Conversa não acessível (verifique permissões de departamento)'
                }, status=status.HTTP_403_FORBIDDEN)
            except Conversation.DoesNotExist:
                # Conversa realmente não existe
                logger.warning(f"⚠️ [MESSAGES] Conversa {pk} não existe para tenant {request.user.tenant.id}")
                return Response({
                    'results': [],
                    'count': 0,
                    'limit': int(request.query_params.get('limit', 15)),
                    'offset': int(request.query_params.get('offset', 0)),
                    'has_more': False,
                    'next': None,
                    'previous': None,
                    'error': 'Conversa não encontrada'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Paginação
        limit = int(request.query_params.get('limit', 15))  # Default 15 mensagens
        offset = int(request.query_params.get('offset', 0))
        
        # ✅ PERFORMANCE: Usar annotate para contar total junto com a query principal
        # ou fazer count() apenas uma vez antes de buscar mensagens
        # Buscar mensagens com paginação (ordenado por created_at DESC para pegar mais recentes)
        # ✅ CORREÇÃO: Prefetch de reações para incluir reactions e reactions_summary
        messages = Message.objects.filter(
            conversation=conversation
        ).select_related(
            'sender', 'conversation', 'conversation__tenant', 'conversation__department'
        ).prefetch_related(
            'attachments',
            'reactions__user'  # ✅ CORREÇÃO: Prefetch de reações para exibir corretamente
        ).order_by('-created_at')[offset:offset+limit]
        
        # Reverter ordem para exibir (mais antigas primeiro, como WhatsApp)
        messages_list = list(messages)
        messages_list.reverse()
        
        # ✅ PERFORMANCE: Contar total apenas se necessário (para paginação)
        # Se não há offset, não precisa contar total
        total_count = None
        if offset > 0 or len(messages_list) == limit:
            total_count = Message.objects.filter(conversation=conversation).count()
        else:
            total_count = offset + len(messages_list)
        
        serializer = MessageSerializer(messages_list, many=True)
        
        return Response({
            'results': serializer.data,
            'count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count,
            'next': f'/chat/conversations/{pk}/messages/?limit={limit}&offset={offset+limit}' if offset + limit < total_count else None,
            'previous': f'/chat/conversations/{pk}/messages/?limit={limit}&offset={max(0, offset-limit)}' if offset > 0 else None
        })
    
    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """
        Transfere conversa para outro agente ou departamento.
        
        Body: {
            "new_department": "uuid" (opcional),
            "new_agent": "uuid" (opcional),
            "reason": "string" (opcional)
        }
        """
        conversation = self.get_object()
        user = request.user
        
        # Validar permissão
        if not (user.is_admin or user.is_gerente):
            return Response(
                {'error': 'Sem permissão para transferir conversas'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_department_id = request.data.get('new_department')
        new_agent_id = request.data.get('new_agent')
        reason = request.data.get('reason', '')
        
        if not new_department_id and not new_agent_id:
            return Response(
                {'error': 'Informe o novo departamento ou agente'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar novo agente pertence ao departamento
        if new_agent_id and new_department_id:
            from apps.authn.models import User
            try:
                agent = User.objects.get(id=new_agent_id)
                if not agent.departments.filter(id=new_department_id).exists():
                    return Response(
                        {'error': 'Agente não pertence ao departamento selecionado'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Agente não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Salvar dados anteriores para log
        old_department = conversation.department
        old_agent = conversation.assigned_to
        
        # Atualizar conversa
        if new_department_id:
            from apps.authn.models import Department
            try:
                new_dept = Department.objects.get(id=new_department_id, tenant=user.tenant)
                conversation.department = new_dept
            except Department.DoesNotExist:
                return Response(
                    {'error': 'Departamento não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if new_agent_id:
            from apps.authn.models import User
            try:
                new_agent = User.objects.get(id=new_agent_id, tenant=user.tenant)
                conversation.assigned_to = new_agent
            except User.DoesNotExist:
                return Response(
                    {'error': 'Agente não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # ✅ FIX: Atualizar status quando transferir para departamento
        if new_department_id:
            conversation.status = 'open'  # Abrir quando transferir para departamento
        
        conversation.save()
        
        # ✅ FIX: Recarregar conversa do banco para garantir dados atualizados
        conversation.refresh_from_db()
        
        # Criar mensagem interna de transferência
        old_dept_name = old_department.name if old_department else 'Inbox'
        new_dept_name = conversation.department.name if conversation.department else 'Sem departamento'
        old_agent_name = old_agent.get_full_name() if old_agent else 'Não atribuído'
        new_agent_name = conversation.assigned_to.get_full_name() if conversation.assigned_to else 'Não atribuído'
        
        transfer_msg = f"Conversa transferida:\n"
        transfer_msg += f"De: {old_dept_name} ({old_agent_name})\n"
        transfer_msg += f"Para: {new_dept_name} ({new_agent_name})"
        if reason:
            transfer_msg += f"\nMotivo: {reason}"
        
        Message.objects.create(
            conversation=conversation,
            sender=user,
            content=transfer_msg,
            direction='outgoing',
            status='sent',
            is_internal=True
        )
        
        # ✅ NOVO: Enviar mensagem automática de transferência para o cliente
        if new_department_id and conversation.department and conversation.department.transfer_message:
            try:
                import httpx
                from apps.notifications.models import WhatsAppInstance
                from apps.connections.models import EvolutionConnection
                
                # Buscar instância WhatsApp ativa
                wa_instance = WhatsAppInstance.objects.filter(
                    tenant=user.tenant,
                    is_active=True,
                    status='active'
                ).first()
                
                # Buscar servidor Evolution
                evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
                
                if wa_instance and evolution_server:
                    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                    api_key = wa_instance.api_key or evolution_server.api_key
                    instance_name = wa_instance.instance_name
                    
                    # Preparar mensagem de transferência
                    transfer_message_text = conversation.department.transfer_message
                    
                    # Enviar via Evolution API
                    with httpx.Client(timeout=10.0) as client:
                        response = client.post(
                            f"{base_url}/message/sendText/{instance_name}",
                            json={
                                'number': conversation.contact_phone.replace('@g.us', '').replace('@s.whatsapp.net', ''),
                                'text': transfer_message_text
                            },
                            headers={'apikey': api_key, 'Content-Type': 'application/json'}
                        )
                        
                        if response.status_code in [200, 201]:
                            logger.info(
                                f"✅ [TRANSFER] Mensagem automática enviada para {conversation.contact_phone} "
                                f"(departamento: {conversation.department.name})"
                            )
                        else:
                            logger.warning(
                                f"⚠️ [TRANSFER] Erro ao enviar mensagem automática: {response.status_code}"
                            )
                else:
                    logger.warning(
                        f"⚠️ [TRANSFER] Instância WhatsApp ou Evolution não encontrada - "
                        f"mensagem automática não enviada"
                    )
            except Exception as e:
                logger.error(
                    f"❌ [TRANSFER] Erro ao enviar mensagem automática: {e}",
                    exc_info=True
                )
        
        # ✅ FIX: Serializar conversa atualizada para resposta e WebSocket
        serializer = ConversationSerializer(conversation)
        conversation_data = serializer.data
        
        # Broadcast via WebSocket para atualizar conversa em todos os clientes
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.utils.serialization import serialize_conversation_for_ws
        
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        tenant_group = f"chat_tenant_{conversation.tenant_id}"
        
        # ✅ FIX: Broadcast para a sala da conversa (atualiza chat aberto)
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'conversation_transferred',
                'conversation_id': str(conversation.id),
                'new_agent': conversation.assigned_to.email if conversation.assigned_to else None,
                'new_department': conversation.department.name if conversation.department else None,
                'transferred_by': user.email
            }
        )
        
        # ✅ FIX: Broadcast para todo o tenant (atualiza lista de conversas)
        conv_data_serializable = serialize_conversation_for_ws(conversation)
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {
                'type': 'conversation_updated',
                'conversation': conv_data_serializable
            }
        )
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"✅ [TRANSFER] Conversa {conversation.id} transferida por {user.email} "
            f"para {conversation.department.name if conversation.department else 'Sem departamento'}"
        )
        logger.info(f"   📋 Departamento: {conversation.department_id}")
        logger.info(f"   📊 Status: {conversation.status}")
        
        return Response(
            conversation_data,  # ✅ FIX: Usar conversation_data já serializado
            status=status.HTTP_200_OK
        )


class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet para mensagens.
    
    Filtra automaticamente por conversas acessíveis ao usuário.
    """
    
    queryset = Message.objects.select_related(
        'conversation',
        'conversation__tenant',
        'conversation__department',
        'sender'
    ).prefetch_related('attachments')
    permission_classes = [IsAuthenticated, CanAccessChat]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['conversation', 'direction', 'status', 'is_internal']
    ordering_fields = ['created_at']
    ordering = ['created_at']
    
    def get_serializer_class(self):
        """Usa serializer específico para criação."""
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer
    
    @action(detail=True, methods=['post'], url_path='delete')
    def delete_message(self, request, pk=None):
        """
        Apaga uma mensagem no WhatsApp via Evolution API.
        
        ✅ CORREÇÃO: Apenas mensagens próprias (outgoing) podem ser apagadas.
        Mensagens incoming não podem ser apagadas pelo usuário.
        """
        message = self.get_object()
        user = request.user
        
        logger.info(f"🗑️ [DELETE MESSAGE] Requisição recebida:")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Message ID Evolution: {message.message_id}")
        logger.info(f"   Direction: {message.direction}")
        logger.info(f"   Is Deleted: {message.is_deleted}")
        logger.info(f"   Tenant ID: {message.conversation.tenant_id}")
        logger.info(f"   User Tenant ID: {user.tenant_id}")
        
        # Verificar se mensagem pertence ao tenant do usuário
        if message.conversation.tenant_id != user.tenant_id:
            logger.warning(f"⚠️ [DELETE MESSAGE] Mensagem não pertence ao tenant do usuário")
            return Response(
                {'error': 'Mensagem não pertence ao seu tenant'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar se mensagem já está apagada
        if message.is_deleted:
            logger.warning(f"⚠️ [DELETE MESSAGE] Mensagem já está apagada")
            return Response(
                {'error': 'Mensagem já está apagada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se mensagem tem message_id (Evolution ID)
        if not message.message_id:
            logger.warning(f"⚠️ [DELETE MESSAGE] Mensagem não tem message_id (Evolution ID)")
            return Response(
                {'error': 'Mensagem não pode ser apagada (não tem ID da Evolution)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CORREÇÃO: Apenas mensagens próprias (outgoing) podem ser apagadas
        # Mensagens incoming não podem ser apagadas pelo usuário
        if message.direction == 'incoming':
            logger.warning(f"⚠️ [DELETE MESSAGE] Tentativa de apagar mensagem recebida (incoming)")
            return Response(
                {'error': 'Não é possível apagar mensagens recebidas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar instância WhatsApp ativa
        from apps.notifications.models import WhatsAppInstance
        from apps.connections.models import EvolutionConnection
        from django.utils import timezone
        import httpx
        
        instance = WhatsAppInstance.objects.filter(
            tenant=message.conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not instance:
            return Response(
                {'error': 'Nenhuma instância WhatsApp ativa'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server and not instance.api_url:
            return Response(
                {'error': 'Configuração da Evolution API não encontrada'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Preparar URL e credenciais
        base_url = (instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = instance.api_key or evolution_server.api_key
        instance_name = instance.instance_name
        
        # ✅ CORREÇÃO: Endpoint correto da Evolution API
        # Documentação: https://doc.evolution-api.com/v2/api-reference/chat-controller/delete-message-for-everyone
        # Método: DELETE (não POST!)
        # Path: /chat/deleteMessageForEveryone/{instance}
        endpoint = f"{base_url}/chat/deleteMessageForEveryone/{instance_name}"
        
        # Preparar remoteJid
        conversation = message.conversation
        if conversation.conversation_type == 'group':
            # Para grupos, usar o group_jid do group_metadata
            group_metadata = conversation.group_metadata or {}
            remote_jid = group_metadata.get('group_id') or conversation.contact_phone
            if '@' not in remote_jid:
                remote_jid = f"{remote_jid}@g.us"
        else:
            # Para individuais, usar contact_phone
            phone = conversation.contact_phone.replace('+', '')
            remote_jid = f"{phone}@s.whatsapp.net"
        
        # Payload conforme documentação da Evolution API
        payload = {
            'id': message.message_id,
            'remoteJid': remote_jid,
            'fromMe': message.direction == 'outgoing',
        }
        
        # Adicionar participant apenas para grupos
        if conversation.conversation_type == 'group':
            # Para grupos, participant é opcional mas pode ser necessário
            # Usar o número da instância ou deixar vazio
            participant = None  # Evolution API pode inferir do remoteJid
            if participant:
                payload['participant'] = participant
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        # Importar funções de mascaramento
        from apps.chat.webhooks import _mask_digits, _mask_remote_jid
        
        logger.info(f"🗑️ [DELETE MESSAGE] Apagando mensagem via Evolution API:")
        logger.info(f"   Endpoint: {endpoint}")
        logger.info(f"   Método: DELETE")
        logger.info(f"   Message ID: {_mask_digits(message.message_id)}")
        logger.info(f"   Remote JID: {_mask_remote_jid(remote_jid)}")
        logger.info(f"   From Me: {payload['fromMe']}")
        
        try:
            # Chamar Evolution API com método DELETE
            # ✅ CORREÇÃO: httpx.delete() não aceita json=, mas request() aceita
            with httpx.Client(timeout=10.0) as client:
                response = client.request(
                    method='DELETE',
                    url=endpoint,
                    json=payload,  # httpx.request() aceita json= diretamente
                    headers=headers
                )
                
                if response.status_code in (200, 201):
                    # Marcar como apagada no banco
                    message.is_deleted = True
                    message.deleted_at = timezone.now()
                    message.save(update_fields=['is_deleted', 'deleted_at'])
                    
                    logger.info(f"✅ [DELETE MESSAGE] Mensagem apagada com sucesso: {message.id}")
                    
                    # Broadcast via WebSocket
                    from apps.chat.utils.websocket import broadcast_message_deleted
                    broadcast_message_deleted(message)
                    
                    return Response(
                        {'status': 'success', 'message': 'Mensagem apagada com sucesso'},
                        status=status.HTTP_200_OK
                    )
                else:
                    logger.error(f"❌ [DELETE MESSAGE] Erro {response.status_code} ao apagar mensagem:")
                    logger.error(f"   Response: {response.text[:200]}")
                    return Response(
                        {'error': f'Erro ao apagar mensagem: {response.status_code}', 'details': response.text[:200]},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            logger.error(f"❌ [DELETE MESSAGE] Erro ao apagar mensagem: {e}", exc_info=True)
            return Response(
                {'error': f'Erro ao apagar mensagem: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='forward')
    def forward_message(self, request, pk=None):
        """
        Encaminha uma mensagem para outra conversa via Evolution API.
        
        Body:
        {
            "conversation_id": "uuid-da-conversa-destino"
        }
        
        Documentação Evolution API:
        POST /chat/forwardMessage/{instance}
        {
            "number": "5517999999999",
            "messageId": "message_id_evolution"
        }
        """
        message = self.get_object()
        user = request.user
        
        # Verificar se mensagem pertence ao tenant do usuário
        if message.conversation.tenant_id != user.tenant_id:
            return Response(
                {'error': 'Mensagem não pertence ao seu tenant'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar se mensagem tem message_id (Evolution ID)
        if not message.message_id:
            return Response(
                {'error': 'Mensagem não pode ser encaminhada (não tem ID da Evolution)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar conversa destino
        destination_conversation_id = request.data.get('conversation_id')
        if not destination_conversation_id:
            return Response(
                {'error': 'conversation_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            destination_conversation = Conversation.objects.get(
                id=destination_conversation_id,
                tenant=user.tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversa destino não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar se não está encaminhando para a mesma conversa
        if destination_conversation.id == message.conversation.id:
            return Response(
                {'error': 'Não é possível encaminhar para a mesma conversa'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar instância WhatsApp ativa
        from apps.notifications.models import WhatsAppInstance
        from apps.connections.models import EvolutionConnection
        import httpx
        
        instance = WhatsAppInstance.objects.filter(
            tenant=message.conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not instance:
            return Response(
                {'error': 'Nenhuma instância WhatsApp ativa'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server and not instance.api_url:
            return Response(
                {'error': 'Configuração da Evolution API não encontrada'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # ✅ CORREÇÃO: Evolution API não tem endpoint específico para encaminhar
        # Solução: Criar nova mensagem e usar fluxo normal de envio (sendText/sendMedia)
        # Isso é mais confiável e funciona para todos os tipos de mensagem
        
        logger.info(f"📤 [FORWARD MESSAGE] Encaminhando mensagem:")
        logger.info(f"   Message ID original: {message.id}")
        logger.info(f"   From conversation: {message.conversation.contact_phone}")
        logger.info(f"   To conversation: {destination_conversation.contact_phone}")
        
        try:
            # Criar mensagem na conversa destino
            forwarded_message = Message.objects.create(
                conversation=destination_conversation,
                sender=user,
                content=message.content or '',
                direction='outgoing',
                status='pending',  # Será atualizado quando enviar
                is_internal=False,
                metadata={
                    'forwarded_from': str(message.id),
                    'forwarded_from_conversation': str(message.conversation.id),
                    'forwarded_at': timezone.now().isoformat(),
                    'original_message_id': message.message_id,
                    'include_signature': True  # Incluir assinatura por padrão
                }
            )
            
            # Se a mensagem original tinha anexos, copiar referências
            attachment_urls = []
            if message.attachments.exists():
                from apps.chat.models import MessageAttachment
                for original_attachment in message.attachments.all():
                    MessageAttachment.objects.create(
                        message=forwarded_message,
                        file_url=original_attachment.file_url,
                        short_url=original_attachment.short_url,
                        mime_type=original_attachment.mime_type,
                        original_filename=original_attachment.original_filename,
                        file_size=original_attachment.file_size
                    )
                    # Adicionar URL para envio
                    attachment_urls.append(original_attachment.short_url or original_attachment.file_url)
                
                forwarded_message.metadata['attachment_urls'] = attachment_urls
                forwarded_message.save(update_fields=['metadata'])
            
            logger.info(f"✅ [FORWARD MESSAGE] Mensagem criada: {forwarded_message.id}")
            
            # Enfileirar envio via fluxo normal (send_message_to_evolution)
            from apps.chat.tasks import send_message_to_evolution
            send_message_to_evolution.delay(str(forwarded_message.id))
            
            logger.info(f"✅ [FORWARD MESSAGE] Mensagem enfileirada para envio: {forwarded_message.id}")
            
            # Broadcast via WebSocket (mensagem pendente)
            from apps.chat.utils.websocket import broadcast_message_received
            broadcast_message_received(forwarded_message)
            
            return Response(
                {
                    'status': 'success',
                    'message': 'Mensagem encaminhada com sucesso',
                    'forwarded_message_id': str(forwarded_message.id)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"❌ [FORWARD MESSAGE] Erro ao encaminhar mensagem: {e}", exc_info=True)
            return Response(
                {'error': f'Erro ao encaminhar mensagem: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_queryset(self):
        """
        Filtra mensagens por conversas acessíveis ao usuário.
        
        ✅ CORREÇÃO: Prefetch de reações em batch para evitar N+1 queries.
        """
        from apps.chat.models import MessageReaction
        
        queryset = self.queryset
        
        # ✅ CORREÇÃO: Prefetch de reações em batch
        # Usar prefetch normal (sem to_attr) para manter compatibilidade com serializer
        queryset = queryset.prefetch_related('reactions__user')
        
        user = self.request.user
        
        if user.is_superuser:
            return queryset
        
        if user.is_admin:
            return queryset.filter(conversation__tenant=user.tenant)
        
        # Gerente/Agente: apenas mensagens de conversas dos seus departamentos
        user_departments = user.departments.all()
        if not user_departments.exists():
            return queryset.none()
        
        return queryset.filter(
            conversation__tenant=user.tenant,
            conversation__department__in=user_departments
        )


class MessageReactionViewSet(viewsets.ViewSet):
    """
    ViewSet para reações de mensagens.
    
    Permite adicionar/remover reações (emoji) a mensagens.
    
    ✅ CORREÇÃO: Usar ViewSet ao invés de ModelViewSet para evitar rotas padrão conflitantes.
    Isso garante que apenas os actions customizados (add/remove) sejam expostos.
    """
    
    from apps.chat.models import MessageReaction, Message
    from apps.chat.api.serializers import MessageReactionSerializer
    
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    @action(detail=False, methods=['get'], url_path='queues/status')
    def queues_status(self, request):
        """
        ✅ CORREÇÃO: Endpoint de métricas e monitoramento de filas Redis.
        
        Retorna:
        {
            "metrics": {
                "send_message": {"length": 10, "name": "..."},
                "fetch_profile_pic": {"length": 5, "name": "..."},
                "fetch_group_info": {"length": 2, "name": "..."},
                "dead_letter": {"length": 1, "name": "..."},
                "total": 18
            },
            "alerts": ["⚠️ Fila send_message tem 1500 mensagens (acima de 1000)"],
            "timestamp": "2025-11-04T..."
        }
        """
        from apps.chat.redis_streams import get_stream_metrics

        queue_metrics = get_queue_metrics()
        stream_metrics = get_stream_metrics()

        alerts = []
        for queue_name, queue_data in queue_metrics.items():
            if isinstance(queue_data, dict) and queue_data.get('length', 0) > 1000:
                alerts.append(f"⚠️ Fila {queue_name} tem {queue_data['length']} mensagens (acima de 1000)")

        send_stream = stream_metrics.get('send_message_stream', {})
        if send_stream.get('length', 0) > 200:
            alerts.append(f"⚠️ Stream de envio tem {send_stream['length']} pendências (acima de 200)")

        mark_stream = stream_metrics.get('mark_as_read_stream', {})
        if mark_stream.get('length', 0) > 200:
            alerts.append(f"⚠️ Stream mark_as_read tem {mark_stream['length']} pendências (acima de 200)")

        return Response({
            'metrics': queue_metrics,
            'stream_metrics': stream_metrics,
            'alerts': alerts,
            'timestamp': timezone.now().isoformat()
        })
    
    @action(detail=False, methods=['post'], url_path='add')
    def add_reaction(self, request):
        """
        Adiciona uma reação a uma mensagem.
        
        Body:
        {
            "message_id": "uuid",
            "emoji": "👍"
        }
        """
        # ✅ CORREÇÃO: Importar threading no início da função para evitar problemas de escopo
        import threading as threading_module
        
        from apps.chat.models import MessageReaction, Message
        from apps.chat.api.serializers import MessageReactionSerializer
        
        message_id = request.data.get('message_id')
        emoji = request.data.get('emoji', '').strip()
        
        if not message_id:
            return Response(
                {'error': 'message_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not emoji:
            return Response(
                {'error': 'emoji é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CORREÇÃO: Validação de emoji (segurança)
        import unicodedata
        # Verificar se é realmente um emoji (não apenas string)
        # Emojis têm categoria Unicode 'So' (Symbol, other) ou 'Sk' (Symbol, modifier)
        if len(emoji) > 10:  # Limite de 10 caracteres (alguns emojis são compostos)
            return Response(
                {'error': 'Emoji inválido (muito longo)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se todos os caracteres são emojis válidos
        for char in emoji:
            category = unicodedata.category(char)
            if category not in ('So', 'Sk', 'Mn', 'Mc'):  # Symbol, Modifier
                # Permitir alguns caracteres especiais comuns em emojis (variation selectors)
                if ord(char) < 0x1F300 and char not in ('\uFE0F', '\u200D'):  # Emojis começam em U+1F300
                    return Response(
                        {'error': 'Emoji inválido (caracteres não permitidos)'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Validar que mensagem existe e é acessível
        try:
            message = Message.objects.select_related('conversation', 'conversation__tenant').get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Mensagem não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar acesso à conversa
        if message.conversation.tenant != request.user.tenant:
            logger.warning(f"⚠️ [REACTION] Acesso negado - Tenant diferente. Mensagem tenant: {message.conversation.tenant.id}, User tenant: {request.user.tenant.id}")
            return Response(
                {'error': 'Acesso negado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar se usuário tem acesso ao departamento (se não for admin)
        # ✅ CORREÇÃO: Se conversa não tem departamento (Inbox), qualquer usuário pode reagir
        if not request.user.is_admin and not request.user.is_superuser:
            if message.conversation.department and message.conversation.department not in request.user.departments.all():
                logger.warning(f"⚠️ [REACTION] Acesso negado - Usuário {request.user.email} não tem acesso ao departamento {message.conversation.department.name}")
                return Response(
                    {'error': 'Acesso negado ao departamento'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # ✅ CORREÇÃO CRÍTICA: Validar que mensagem tem message_id (ID externo do WhatsApp)
        # Sem message_id, não é possível enviar reação para Evolution API
        if not message.message_id:
            logger.warning(f"⚠️ [REACTION] Mensagem {message.id} não tem message_id")
            return Response(
                {'error': 'Mensagem não tem message_id (não foi enviada pelo sistema ou ainda não foi processada)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CORREÇÃO CRÍTICA: Buscar número da instância WhatsApp conectada
        # A reação deve ser criada com external_sender = número da instância, não com user=request.user
        # Isso garante que aparece como vindo do número da instância (como no WhatsApp)
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance or not wa_instance.phone_number:
            logger.warning(f"⚠️ [REACTION] Instância WhatsApp não encontrada - Tenant: {request.user.tenant.id}, is_active=True, status=active")
            return Response(
                {'error': 'Instância WhatsApp não encontrada ou não conectada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance_phone = wa_instance.phone_number
        logger.info(f"📱 [REACTION] Usando número da instância para reação: {instance_phone}")
        
        # ✅ CORREÇÃO CRÍTICA: Comportamento estilo WhatsApp - substituir reação anterior
        # Buscar reação existente pelo número da instância (não pelo user)
        existing_reaction = MessageReaction.objects.filter(
            message=message,
            external_sender=instance_phone,
            user__isnull=True
        ).first()
        
        if existing_reaction:
            if existing_reaction.emoji == emoji:
                # ✅ Se é o mesmo emoji, remover (toggle off)
                old_emoji = existing_reaction.emoji
                existing_reaction.delete()
                logger.info(f"✅ [REACTION] Reação removida (toggle off): {instance_phone} {emoji} em {message.id}")
                
                # ✅ CORREÇÃO CRÍTICA: Enviar remoção para Evolution API (WhatsApp)
                # Enviar reação vazia remove a reação no WhatsApp
                from apps.chat.tasks import send_reaction_to_evolution
                
                def remove_reaction_async():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        # ✅ Enviar emoji vazio remove a reação no WhatsApp
                        loop.run_until_complete(send_reaction_to_evolution(message, ''))
                        loop.close()
                        logger.info(f"✅ [REACTION] Remoção enviada para Evolution API: {instance_phone} removendo {old_emoji} em {message.id}")
                    except Exception as e:
                        logger.error(f"⚠️ [REACTION] Erro ao enviar remoção para Evolution API: {e}", exc_info=True)
                
                # ✅ CORREÇÃO: threading_module já importado no início da função
                thread = threading_module.Thread(target=remove_reaction_async, daemon=True)
                thread.start()
                
                # Broadcast atualização após remover
                message = Message.objects.prefetch_related('reactions__user').get(id=message.id)
                from apps.chat.utils.websocket import broadcast_message_reaction_update
                broadcast_message_reaction_update(message)
                
                return Response({'success': True, 'removed': True}, status=status.HTTP_200_OK)
            else:
                # ✅ Se é emoji diferente, remover reação antiga no WhatsApp primeiro, depois criar nova
                old_emoji = existing_reaction.emoji
                existing_reaction.delete()
                logger.info(f"✅ [REACTION] Reação antiga removida para substituir: {instance_phone} {old_emoji} → {emoji}")
                
                # ✅ CORREÇÃO CRÍTICA: Remover reação antiga no WhatsApp antes de enviar nova
                from apps.chat.tasks import send_reaction_to_evolution
                
                def remove_old_reaction_async():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        # Remover reação antiga primeiro
                        loop.run_until_complete(send_reaction_to_evolution(message, ''))
                        loop.close()
                        logger.info(f"✅ [REACTION] Reação antiga removida no WhatsApp: {old_emoji}")
                    except Exception as e:
                        logger.error(f"⚠️ [REACTION] Erro ao remover reação antiga no WhatsApp: {e}", exc_info=True)
                
                # ✅ CORREÇÃO: threading_module já importado no início da função
                thread = threading_module.Thread(target=remove_old_reaction_async, daemon=True)
                thread.start()
        
        # ✅ CORREÇÃO CRÍTICA: Criar reação com external_sender = número da instância (NÃO com user=request.user)
        # Isso garante que aparece como vindo do número da instância (como no WhatsApp)
        reaction, created = MessageReaction.objects.update_or_create(
            message=message,
            external_sender=instance_phone,
            user=None,  # ✅ Sempre None para reações da instância
            defaults={'emoji': emoji}
        )
        
        # ✅ CORREÇÃO CRÍTICA: Enviar reação para Evolution API (WhatsApp)
        # Isso garante que a reação aparece no WhatsApp do destinatário
        # ✅ CORREÇÃO: Executar de forma assíncrona em thread separada para não bloquear resposta
        from apps.chat.tasks import send_reaction_to_evolution
        
        # ✅ CORREÇÃO: Executar envio de reação em thread separada com melhor tratamento de erros
        # Usar threading com tratamento robusto de erros e logs detalhados
        def send_reaction_async():
            """Executa envio de reação de forma assíncrona em thread separada."""
            try:
                logger.info(f"🔄 [REACTION THREAD] Iniciando envio de reação: {emoji} em {message.id}")
                
                # Criar novo event loop para esta thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Executar função assíncrona
                    result = loop.run_until_complete(send_reaction_to_evolution(message, emoji))
                    
                    if result:
                        logger.info(f"✅ [REACTION THREAD] Reação enviada com SUCESSO para Evolution API: {request.user.email} {emoji} em {message.id}")
                    else:
                        logger.warning(f"⚠️ [REACTION THREAD] Reação NÃO foi enviada (retornou False): {emoji} em {message.id}")
                finally:
                    # Sempre fechar o loop
                    loop.close()
                    logger.debug(f"🔌 [REACTION THREAD] Event loop fechado")
                    
            except httpx.TimeoutException as e:
                logger.error(f"❌ [REACTION THREAD] Timeout ao enviar reação: {e}")
                logger.error(f"   Message ID: {message.id}, Emoji: {emoji}")
            except httpx.ReadTimeout as e:
                logger.error(f"❌ [REACTION THREAD] ReadTimeout ao enviar reação: {e}")
                logger.error(f"   Message ID: {message.id}, Emoji: {emoji}")
            except Exception as e:
                # Logar TODOS os erros com traceback completo para debug
                logger.error(f"❌ [REACTION THREAD] Erro inesperado ao enviar reação para Evolution API: {e}", exc_info=True)
                logger.error(f"   Message ID: {message.id}, Emoji: {emoji}")
                logger.error(f"   Tipo de erro: {type(e).__name__}")
        
        # Executar em thread separada para não bloquear resposta HTTP
        # ✅ CORREÇÃO: threading_module já importado no início da função
        thread = threading_module.Thread(target=send_reaction_async, daemon=True, name=f"ReactionSender-{message.id}")
        thread.start()
        logger.info(f"🚀 [REACTION] Thread iniciada para envio de reação: {emoji} em {message.id}")
        
        # ✅ CORREÇÃO CRÍTICA: Broadcast WebSocket sempre (mesmo se reação já existe)
        # Usar função helper que faz broadcast para tenant inteiro
        from apps.chat.utils.websocket import broadcast_message_reaction_update
        
        try:
            # ✅ CORREÇÃO: Prefetch de reações antes de serializar
            # Recarregar mensagem com prefetch de reações para evitar race conditions
            message = Message.objects.prefetch_related('reactions__user').get(id=message.id)
            
            # ✅ CORREÇÃO: Não passar reaction_data - o broadcast vai usar a mensagem completa com todas as reações
            # A reação agora é com external_sender (número da instância), não com user
            broadcast_message_reaction_update(message)
            
            if created:
                logger.info(f"✅ [REACTION] Reação adicionada: {instance_phone} {emoji} em {message.id}")
            else:
                logger.info(f"✅ [REACTION] Reação já existente (broadcast): {instance_phone} {emoji} em {message.id}")
        except Exception as e:
            logger.error(f"❌ [REACTION] Erro ao fazer broadcast: {e}", exc_info=True)
        
        serializer = MessageReactionSerializer(reaction)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)
    
    @action(detail=False, methods=['post'], url_path='remove')
    def remove_reaction(self, request):
        """
        Remove uma reação de uma mensagem.
        
        Body:
        {
            "message_id": "uuid",
            "emoji": "👍"
        }
        """
        # ✅ CORREÇÃO: Importar threading no início da função para evitar problemas de escopo
        import threading as threading_module
        
        from apps.chat.models import MessageReaction, Message
        from apps.chat.utils.websocket import broadcast_message_reaction_update
        
        message_id = request.data.get('message_id')
        emoji = request.data.get('emoji', '').strip()
        
        if not message_id:
            return Response(
                {'error': 'message_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not emoji:
            return Response(
                {'error': 'emoji é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar que mensagem existe e é acessível
        try:
            message = Message.objects.select_related('conversation', 'conversation__tenant').get(id=message_id)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Mensagem não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar acesso à conversa
        if message.conversation.tenant != request.user.tenant:
            return Response(
                {'error': 'Acesso negado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar se usuário tem acesso ao departamento (se não for admin)
        if not request.user.is_admin and not request.user.is_superuser:
            if message.conversation.department and message.conversation.department not in request.user.departments.all():
                return Response(
                    {'error': 'Acesso negado ao departamento'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # ✅ CORREÇÃO CRÍTICA: Validar que mensagem tem message_id antes de remover
        if not message.message_id:
            return Response(
                {'error': 'Mensagem não tem message_id (não foi enviada pelo sistema ou ainda não foi processada)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CORREÇÃO CRÍTICA: Buscar número da instância WhatsApp conectada
        # A reação deve ser removida pelo número da instância, não pelo user
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance or not wa_instance.phone_number:
            return Response(
                {'error': 'Instância WhatsApp não encontrada ou não conectada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance_phone = wa_instance.phone_number
        
        # Remover reação (se existir) - buscar pelo número da instância
        try:
            reaction = MessageReaction.objects.get(
                message=message,
                external_sender=instance_phone,
                user__isnull=True,
                emoji=emoji
            )
            reaction.delete()
            
            # ✅ CORREÇÃO CRÍTICA: Enviar remoção para Evolution API (WhatsApp)
            # Enviar reação vazia remove a reação no WhatsApp
            # ✅ CORREÇÃO: asyncio já está importado no topo do arquivo
            from apps.chat.tasks import send_reaction_to_evolution
            
            def remove_reaction_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    # ✅ Enviar emoji vazio remove a reação no WhatsApp
                    loop.run_until_complete(send_reaction_to_evolution(message, ''))
                    loop.close()
                    logger.info(f"✅ [REACTION] Remoção enviada para Evolution API: {instance_phone} removendo {emoji} em {message.id}")
                except Exception as e:
                    logger.error(f"⚠️ [REACTION] Erro ao enviar remoção para Evolution API: {e}", exc_info=True)
            
            # ✅ CORREÇÃO: threading_module já importado no início da função
            thread = threading_module.Thread(target=remove_reaction_async, daemon=True)
            thread.start()
            
            # ✅ CORREÇÃO CRÍTICA: Broadcast WebSocket após remover reação
            # Recarregar mensagem com prefetch de reações
            message = Message.objects.prefetch_related('reactions__user').get(id=message.id)
            broadcast_message_reaction_update(message)
            
            logger.info(f"✅ [REACTION] Reação removida: {instance_phone} {emoji} em {message.id}")
            
            return Response({'success': True}, status=status.HTTP_200_OK)
        except MessageReaction.DoesNotExist:
            return Response(
                {'error': 'Reação não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanAccessChat])
def chat_metrics_overview(request):
    """
    Retorna snapshot das filas Redis e métricas de integração com a Evolution.
    """
    worker_status = get_worker_status()
    configured_workers = {
        'send_message': max(1, int(os.getenv('CHAT_SEND_MESSAGE_WORKERS', '3'))),
    }

    return Response({
        'queues': get_queue_metrics(),
        'latencies': get_metrics(),
        'workers': {
            'configured': configured_workers,
            'status': worker_status,
        },
        'timestamp': timezone.now().isoformat()
    })


class UploadPresignedUrlView(APIView):
    """
    View baseada em classe para upload-presigned-url (rota customizada).
    Gera presigned URL para upload direto no S3/MinIO.
    """
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    def post(self, request):
        import logging
        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from apps.chat.utils.s3 import S3Manager
        from apps.chat.models import Conversation
        from django.conf import settings
        
        logger = logging.getLogger(__name__)
        
        # Log CRÍTICO para debug - se isso aparecer, a função está sendo chamada
        logger.error(f"🚨 [PRESIGNED VIEW] FUNÇÃO CHAMADA! method={request.method}, path={request.path}, user={request.user.email if hasattr(request, 'user') else 'None'}")
        
        # Log para debug
        logger.info(f"📤 [PRESIGNED] Recebido request: method={request.method}, path={request.path}, data={request.data}")
        
        # Validar dados
        conversation_id = request.data.get('conversation_id')
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size', 0)
        
        if not all([conversation_id, filename, content_type]):
            return Response(
                {'error': 'conversation_id, filename e content_type são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamanho (max do settings)
        max_size = int(getattr(settings, 'ATTACHMENTS_MAX_SIZE_MB', 50)) * 1024 * 1024
        if file_size > max_size:
            return Response(
                {'error': f'Arquivo muito grande. Máximo: {max_size / 1024 / 1024}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar MIME
        allowed_mime = getattr(settings, 'ATTACHMENTS_ALLOWED_MIME', '')
        if allowed_mime:
            allowed = [m.strip() for m in allowed_mime.split(',') if m.strip()]
            def mime_ok(m):
                return any((a.endswith('/*') and m.startswith(a[:-1])) or (a == m) for a in allowed)
            if not mime_ok(content_type):
                return Response(
                    {'error': 'Tipo de arquivo não permitido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Buscar conversa
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                tenant=request.user.tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversa não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Gerar caminho S3
        attachment_id = uuid.uuid4()
        file_ext = filename.split('.')[-1] if '.' in filename else ''
        s3_key = f"chat/{request.user.tenant.id}/attachments/{attachment_id}.{file_ext}"
        
        # Gerar presigned URL
        try:
            s3_manager = S3Manager()
            expires_upload = int(getattr(settings, 'S3_UPLOAD_URL_EXPIRES', 300))
            upload_url = s3_manager.generate_presigned_url(
                s3_key,
                expiration=expires_upload,
                http_method='PUT'
            )
            
            logger.info(f"✅ [PRESIGNED] URL gerada: {s3_key}")
            
            return Response({
                'upload_url': upload_url,
                'attachment_id': str(attachment_id),
                's3_key': s3_key,
                'expires_in': expires_upload,
                'instructions': {
                    'method': 'PUT',
                    'headers': {
                        'Content-Type': content_type
                    }
                }
            })
        
        except Exception as e:
            logger.error(f"❌ [PRESIGNED] Erro ao gerar URL: {e}", exc_info=True)
            return Response(
                {'error': f'Erro ao gerar URL de upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

def chat_ping_evolution(request):
    """
    Executa um ping simples na Evolution API para medir latência em tempo real.
    Aceita query-param opcional `instance` com UUID da instância.
    """
    from django.conf import settings
    import httpx

    tenant = request.user.tenant
    instance_id = request.query_params.get('instance')

    instance_qs = WhatsAppInstance.objects.filter(
        tenant=tenant,
        is_active=True
    )
    if instance_id:
        instance_qs = instance_qs.filter(id=instance_id)

    wa_instance = instance_qs.first()
    if not wa_instance:
        return Response(
            {'error': 'Nenhuma instância WhatsApp ativa encontrada para o tenant'},
            status=status.HTTP_404_NOT_FOUND
        )

    evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
    if not evolution_server and not wa_instance.api_url:
        return Response(
            {'error': 'Configuração da Evolution API não encontrada'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
    health_path = getattr(settings, 'EVOLUTION_HEALTHCHECK_PATH', '/health')
    health_path = '/' + health_path.lstrip('/')
    url = f"{base_url}{health_path}"

    request_start = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
        latency = time.perf_counter() - request_start
        record_latency(
            'evolution_ping',
            latency,
            {
                'status_code': response.status_code,
                'instance_name': wa_instance.instance_name,
            }
        )
        return Response({
            'success': response.status_code < 500,
            'status_code': response.status_code,
            'latency_seconds': round(latency, 4),
            'url': url,
            'instance_name': wa_instance.instance_name,
            'timestamp': timezone.now().isoformat(),
        })
    except Exception as exc:
        latency = time.perf_counter() - request_start
        record_error('evolution_ping', str(exc))
        return Response(
            {
                'success': False,
                'error': str(exc),
                'latency_seconds': round(latency, 4),
                'url': url,
                'instance_name': wa_instance.instance_name,
                'timestamp': timezone.now().isoformat(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    def perform_create(self, serializer):
        """
        Cria mensagem e envia para RabbitMQ para processamento assíncrono.
        """
        message = serializer.save()
        
        # ✅ FIX CRÍTICO: Broadcast imediato para adicionar mensagem em tempo real
        # A mensagem aparece imediatamente na conversa (com status 'pending')
        # Depois será atualizada quando for enviada com sucesso
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from apps.chat.utils.serialization import serialize_message_for_ws, serialize_conversation_for_ws
            
            channel_layer = get_channel_layer()
            room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
            tenant_group = f"chat_tenant_{message.conversation.tenant_id}"
            
            msg_data_serializable = serialize_message_for_ws(message)
            conv_data_serializable = serialize_conversation_for_ws(message.conversation)
            
            # ✅ Broadcast para room da conversa (para adicionar mensagem)
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'message_received',
                    'message': msg_data_serializable
                }
            )
            
            # ✅ Broadcast para grupo do tenant (para que useTenantSocket processe)
            async_to_sync(channel_layer.group_send)(
                tenant_group,
                {
                    'type': 'message_received',
                    'message': msg_data_serializable,
                    'conversation': conv_data_serializable
                }
            )
            
            logger.info(f"📡 [MESSAGE CREATE] Mensagem criada e broadcast enviado (ID: {message.id})")
        except Exception as e:
            logger.error(f"❌ [MESSAGE CREATE] Erro ao broadcast mensagem criada: {e}", exc_info=True)
        
        # Importa aqui para evitar circular import
        from apps.chat.tasks import send_message_to_evolution
        
        # Envia para fila RabbitMQ
        send_message_to_evolution.delay(str(message.id))
        
        return message
    
    def create(self, request, *args, **kwargs):
        """
        Override create para retornar o serializer completo na resposta.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = self.perform_create(serializer)
        
        # Retorna com o MessageSerializer completo
        output_serializer = MessageSerializer(message)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    # ❌ REMOVIDO: Endpoint mark_as_seen não usado
    # Frontend usa POST /conversations/{id}/mark_as_read/ para marcar TODAS as mensagens
    # Este endpoint individual nunca era chamado
    
    @action(detail=False, methods=['post'], url_path='upload-presigned-url')
    def get_upload_presigned_url(self, request):
        """
        Gera presigned URL para upload direto no S3/MinIO.
        
        Body:
        {
            "conversation_id": "uuid",
            "filename": "foto.jpg",
            "content_type": "image/jpeg",
            "file_size": 1024000
        }
        
        Returns:
        {
            "upload_url": "https://s3.../...",
            "attachment_id": "uuid",
            "expires_in": 300
        }
        """
        import logging
        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from apps.chat.utils.s3 import S3Manager
        
        logger = logging.getLogger(__name__)
        
        # Log para debug
        logger.info(f"📤 [PRESIGNED] Recebido request: method={request.method}, path={request.path}, data={request.data}")
        
        # Validar dados
        conversation_id = request.data.get('conversation_id')
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size', 0)
        
        if not all([conversation_id, filename, content_type]):
            return Response(
                {'error': 'conversation_id, filename e content_type são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamanho (max do settings)
        from django.conf import settings
        max_size = int(getattr(settings, 'ATTACHMENTS_MAX_SIZE_MB', 50)) * 1024 * 1024
        if file_size > max_size:
            return Response(
                {'error': f'Arquivo muito grande. Máximo: {max_size / 1024 / 1024}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validar MIME
        allowed_mime = getattr(settings, 'ATTACHMENTS_ALLOWED_MIME', '')
        if allowed_mime:
            allowed = [m.strip() for m in allowed_mime.split(',') if m.strip()]
            def mime_ok(m):
                return any((a.endswith('/*') and m.startswith(a[:-1])) or (a == m) for a in allowed)
            if not mime_ok(content_type):
                return Response(
                    {'error': 'Tipo de arquivo não permitido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Buscar conversa
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                tenant=request.user.tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversa não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Gerar caminho S3
        attachment_id = uuid.uuid4()
        file_ext = filename.split('.')[-1] if '.' in filename else ''
        s3_key = f"chat/{request.user.tenant.id}/attachments/{attachment_id}.{file_ext}"
        
        # Gerar presigned URL
        try:
            s3_manager = S3Manager()
            from django.conf import settings
            expires_upload = int(getattr(settings, 'S3_UPLOAD_URL_EXPIRES', 300))
            upload_url = s3_manager.generate_presigned_url(
                s3_key,
                expiration=expires_upload,
                http_method='PUT'
            )
            
            logger.info(f"✅ [PRESIGNED] URL gerada: {s3_key}")
            
            return Response({
                'upload_url': upload_url,
                'attachment_id': str(attachment_id),
                's3_key': s3_key,
                'expires_in': expires_upload,
                'instructions': {
                    'method': 'PUT',
                    'headers': {
                        'Content-Type': content_type
                    }
                }
            })
        
        except Exception as e:
            logger.error(f"❌ [PRESIGNED] Erro ao gerar URL: {e}", exc_info=True)
            return Response(
                {'error': f'Erro ao gerar URL de upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='confirm-upload')
    def confirm_upload_old(self, request):
        """Método antigo - mantido para referência"""
        pass

class ConfirmUploadView(APIView):
    """
    View baseada em classe para confirm-upload (rota customizada).
    Confirma upload e cria MessageAttachment + envia para Evolution API.
    """
    permission_classes = [IsAuthenticated, CanAccessChat]
    
    def post(self, request):
        """
        Confirma upload e cria MessageAttachment + envia para Evolution API.
        
        Body:
        {
            "conversation_id": "uuid",
            "attachment_id": "uuid",
            "s3_key": "chat/.../...",
            "filename": "foto.jpg",
            "content_type": "image/jpeg",
            "file_size": 1024000
        }
        
        Returns:
        {
            "message": {...},
            "attachment": {...}
        }
        """
        import logging
        import uuid
        from django.utils import timezone
        from datetime import timedelta
        from apps.chat.utils.s3 import S3Manager
        from apps.chat.models import Conversation, Message, MessageAttachment
        from apps.chat.api.serializers import MessageSerializer, MessageAttachmentSerializer
        from django.conf import settings
        
        logger = logging.getLogger(__name__)
        
        # Log CRÍTICO para debug
        logger.error(f"🚨 [CONFIRM UPLOAD VIEW] FUNÇÃO CHAMADA! method={request.method}, path={request.path}, user={request.user.email if hasattr(request, 'user') else 'None'}")
        
        # Validar dados
        conversation_id = request.data.get('conversation_id')
        attachment_id = request.data.get('attachment_id')
        s3_key = request.data.get('s3_key')
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size', 0)
        
        if not all([conversation_id, attachment_id, s3_key, filename, content_type]):
            return Response(
                {'error': 'Dados incompletos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar conversa
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                tenant=request.user.tenant
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversa não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 🎵 CONVERTER ÁUDIO OGG/WEBM → MP3 (para compatibilidade universal)
        from apps.chat.utils.audio_converter import should_convert_audio, convert_ogg_to_mp3, get_converted_filename
        
        logger.info(f"🔍 [AUDIO] Verificando se precisa converter...")
        logger.info(f"   Content-Type: {content_type}")
        logger.info(f"   Filename: {filename}")
        logger.info(f"   Should convert: {should_convert_audio(content_type, filename)}")
        
        if should_convert_audio(content_type, filename):
            logger.info(f"🔄 [AUDIO] Detectado áudio OGG/WEBM, convertendo para MP3...")
            
            try:
                # 1. Baixar OGG do S3
                s3_manager = S3Manager()
                success, ogg_data, msg = s3_manager.download_from_s3(s3_key)
                
                if not success:
                    raise Exception(f"Erro ao baixar OGG: {msg}")
                
                # 2. Detectar formato do áudio (WEBM ou OGG)
                source_format = "webm" if ("webm" in content_type.lower() or filename.lower().endswith(".webm")) else "ogg"
                
                # 3. Converter para MP3
                success, mp3_data, msg = convert_ogg_to_mp3(ogg_data, source_format=source_format)
                
                if not success:
                    logger.warning(f"⚠️ [AUDIO] Conversão falhou: {msg}. Usando OGG original.")
                else:
                    # 3. Re-upload MP3 (substituir OGG)
                    mp3_key = s3_key.replace('.ogg', '.mp3').replace('.webm', '.mp3')
                    success, msg = s3_manager.upload_to_s3(mp3_data, mp3_key, 'audio/mpeg')
                    
                    if success:
                        # Deletar OGG antigo
                        s3_manager.delete_from_s3(s3_key)
                        
                        # Atualizar variáveis
                        s3_key = mp3_key
                        content_type = 'audio/mpeg'
                        filename = get_converted_filename(filename)
                        file_size = len(mp3_data)
                        
                        logger.info(f"✅ [AUDIO] Áudio convertido para MP3!")
                    else:
                        logger.warning(f"⚠️ [AUDIO] Erro ao fazer re-upload: {msg}. Usando OGG.")
            
            except Exception as conv_error:
                logger.error(f"❌ [AUDIO] Erro na conversão: {conv_error}. Continuando com OGG.")
        
        # Gerar presigned URL para Evolution API (curta: 1 hora)
        try:
            s3_manager = S3Manager()
            
            # URL para Evolution API baixar o arquivo
            from django.conf import settings
            expires_download = int(getattr(settings, 'S3_DOWNLOAD_URL_EXPIRES', 900))
            evolution_url = s3_manager.generate_presigned_url(
                s3_key,
                expiration=expires_download,
                http_method='GET'
            )
            
            if not evolution_url:
                raise Exception("Não foi possível gerar presigned URL")
            
            # URL pública para exibir no frontend (via proxy)
            file_url = s3_manager.get_public_url(s3_key)
            
            logger.info(f"✅ [UPLOAD] URLs geradas: Evolution + Proxy")
            
        except Exception as url_error:
            logger.error(f"❌ [UPLOAD] Erro ao gerar URLs: {url_error}")
            return Response(
                {'error': f'Erro ao gerar URLs: {str(url_error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Criar mensagem (com UUID próprio)
        import uuid
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content='',  # Vazio, apenas anexo
            direction='outgoing',
            status='pending',
            is_internal=False,
            metadata={
                'attachment_urls': [evolution_url],  # URL para Evolution API
                'attachment_filename': filename
            }
        )
        
        # Criar attachment
        try:
            logger.info(f"📤 [UPLOAD] Criando attachment com ID: {attachment_id}")
            
            # ✅ IMPORTANTE: Criar attachment permitindo que o save() gere o hash único
            # O método save() do modelo já trata colisões de hash automaticamente
            attachment = MessageAttachment(
                id=attachment_id,
                message=message,
                tenant=request.user.tenant,
                original_filename=filename,
                mime_type=content_type,
                file_path=s3_key,
                file_url=file_url,  # URL pública via proxy
                storage_type='s3',
                size_bytes=file_size,
                expires_at=timezone.now() + timedelta(days=365),  # 1 ano
                processing_status='pending'  # Para IA futura
            )
            # ✅ Usar save() para que o método save() do modelo gere o hash único
            attachment.save()
            
            logger.info(f"✅ [UPLOAD] Mensagem + Anexo criados")
            logger.info(f"   Message ID: {message.id}")
            logger.info(f"   Attachment ID: {attachment_id}")
            logger.info(f"   📌 media_hash: {attachment.media_hash}")
            logger.info(f"   📌 short_url: {attachment.short_url}")
            
            # Enfileirar para envio Evolution API
            from apps.chat.tasks import send_message_to_evolution
            send_message_to_evolution.delay(str(message.id))
            logger.info(f"✅ [UPLOAD] Task enfileirada para envio")
            
            # Broadcast via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            group_name = f"chat_tenant_{request.user.tenant.id}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'chat_message',
                    'message': MessageSerializer(message).data
                }
            )
            logger.info(f"✅ [UPLOAD] WebSocket broadcast enviado")
            
            # Retornar resposta
            return Response({
                'message': MessageSerializer(message).data,
                'attachment': MessageAttachmentSerializer(attachment).data
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"❌ [UPLOAD] Erro ao confirmar upload: {e}", exc_info=True)
            # Deletar mensagem se falhou
            message.delete()
            return Response(
                {'error': f'Erro ao confirmar upload: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MessageAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet read-only para anexos.
    """
    
    queryset = MessageAttachment.objects.select_related(
        'message',
        'message__conversation',
        'tenant'
    )
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['message', 'storage_type', 'mime_type']
    
    def get_queryset(self):
        """Filtra anexos por tenant do usuário."""
        user = self.request.user
        
        if user.is_superuser:
            return self.queryset
        
        return self.queryset.filter(tenant=user.tenant)
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """Endpoint legado desativado. Use o fluxo com presigned URL."""
        return Response(
            {
                'error': 'Endpoint de upload desativado. Use /messages/upload-presigned-url e /messages/confirm-upload.'
            },
            status=status.HTTP_410_GONE
        )


# ==========================================
# VIEW FUNCTION PARA PROXY DE FOTOS
# ==========================================

@api_view(['GET', 'OPTIONS'])
@permission_classes([AllowAny])
def profile_pic_proxy_view(request):
    """
    Proxy público para fotos de perfil do WhatsApp com cache Redis.
    Endpoint completamente público (sem autenticação) para permitir carregamento em <img> tags.
    
    Query params:
    - url: URL da foto de perfil
    """
    import httpx
    from django.http import HttpResponse
    from django.core.cache import cache
    import logging
    import hashlib
    
    logger = logging.getLogger(__name__)
    
    # ✅ CORS Preflight: Responder OPTIONS com headers CORS
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24 horas
        return response
    
    profile_url = request.GET.get('url')
    
    if not profile_url:
        logger.warning('🖼️ [PROXY] URL não fornecida')
        return Response(
            {'error': 'URL é obrigatória'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Gerar chave Redis baseada na URL
    cache_key = f"profile_pic:{hashlib.md5(profile_url.encode()).hexdigest()}"
    
    # Tentar buscar do cache Redis
    cached_data = cache.get(cache_key)
    
    if cached_data:
        logger.info(f'✅ [PROXY CACHE] Imagem servida do Redis: {profile_url[:80]}...')
        
        http_response = HttpResponse(
            cached_data['content'],
            content_type=cached_data['content_type']
        )
        http_response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
        http_response['Access-Control-Allow-Origin'] = '*'
        http_response['X-Cache'] = 'HIT'
        
        return http_response
    
    # Não está no cache, buscar do WhatsApp
    logger.info(f'🔄 [PROXY] Baixando imagem do WhatsApp: {profile_url[:80]}...')
    
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(profile_url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', 'image/jpeg')
            content = response.content
            
            logger.info(f'✅ [PROXY] Imagem baixada! Content-Type: {content_type} | Size: {len(content)} bytes')
            
            # Cachear no Redis por 7 dias
            cache.set(
                cache_key,
                {
                    'content': content,
                    'content_type': content_type
                },
                timeout=604800  # 7 dias
            )
            
            logger.info(f'💾 [PROXY] Imagem cacheada no Redis com chave: {cache_key}')
            
            # Retornar imagem
            http_response = HttpResponse(
                content,
                content_type=content_type
            )
            http_response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
            http_response['Access-Control-Allow-Origin'] = '*'
            http_response['X-Cache'] = 'MISS'
            
            return http_response
    
    except httpx.HTTPStatusError as e:
        logger.error(f'❌ [PROXY] Erro HTTP {e.response.status_code}: {profile_url[:80]}...')
        return Response(
            {'error': f'Erro ao buscar imagem: {e.response.status_code}'},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except Exception as e:
        logger.error(f'❌ [PROXY] Erro: {str(e)} | URL: {profile_url[:80]}...', exc_info=True)
        return Response(
            {'error': f'Erro ao buscar imagem: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
