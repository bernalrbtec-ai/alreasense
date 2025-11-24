"""
Views para o módulo Flow Chat.
Integra com permissões multi-tenant e departamentos.
"""
import logging
import os
from datetime import datetime
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
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
    ordering = ['-last_message_at']
    
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
        
        # Verificar cache (5min)
        cache_key = f"conversation_info_{conversation.id}"
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
                # Montar group_jid corretamente
                raw_phone = conversation.contact_phone
                
                # ✅ USAR JID COMPLETO - Evolution API aceita:
                # - Grupos: xxx@g.us
                # ⚠️ IMPORTANTE: @lid é formato de participante, NÃO de grupo!
                if '@g.us' in raw_phone:
                    # Já tem @g.us, usar como está
                    group_jid = raw_phone
                elif '@s.whatsapp.net' in raw_phone:
                    # Formato errado (individual), corrigir para grupo
                    group_jid = raw_phone.replace('@s.whatsapp.net', '@g.us')
                else:
                    # Adicionar @g.us se não tiver (padrão para grupos)
                    clean_id = raw_phone.replace('+', '').strip()
                    group_jid = f"{clean_id}@g.us"
                
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
                        
                        # Atualizar conversa
                        if group_name and group_name != conversation.contact_name:
                            conversation.contact_name = group_name
                            update_fields.append('contact_name')
                            logger.info(f"✅ [REFRESH GRUPO] Nome: {group_name}")
                        
                        if group_pic_url and group_pic_url != conversation.profile_pic_url:
                            conversation.profile_pic_url = group_pic_url
                            update_fields.append('profile_pic_url')
                            logger.info(f"✅ [REFRESH GRUPO] Foto atualizada")
                        
                        # Atualizar metadados
                        conversation.group_metadata = {
                            'group_id': group_jid,
                            'group_name': group_name,
                            'group_pic_url': group_pic_url,
                            'participants_count': participants_count,
                            'description': group_desc,
                            'is_group': True,
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
        from apps.authn.models import Department
        if department_id:
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
        else:
            # Usar primeiro departamento do tenant ou do usuário
            if request.user.is_admin:
                department = Department.objects.filter(
                    tenant=request.user.tenant
                ).first()
            else:
                department = request.user.departments.first()
            
            if not department:
                return Response(
                    {'error': 'Nenhum departamento disponível'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
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
            
            return Response(
                {
                    'message': 'Conversa já existe',
                    'conversation': ConversationSerializer(existing).data
                },
                status=status.HTTP_200_OK
            )
        
        # Criar nova conversa com telefone normalizado
        conversation = Conversation.objects.create(
            tenant=request.user.tenant,
            department=department,
            contact_phone=normalized_phone,  # ✅ Usar telefone normalizado
            contact_name=contact_name,
            assigned_to=request.user,
            status='open'
        )
        
        # Adicionar usuário como participante
        conversation.participants.add(request.user)
        
        return Response(
            {
                'message': 'Conversa criada com sucesso!',
                'conversation': ConversationSerializer(conversation).data
            },
            status=status.HTTP_201_CREATED
        )
    
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
        
        # Contar total de mensagens (para paginação)
        total_count = Message.objects.filter(conversation=conversation).count()
        
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
                import asyncio
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
                
                import threading
                thread = threading.Thread(target=remove_reaction_async, daemon=True)
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
                import asyncio
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
                
                import threading
                thread = threading.Thread(target=remove_old_reaction_async, daemon=True)
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
        import asyncio
        from apps.chat.tasks import send_reaction_to_evolution
        
        # Executar envio em background (não bloquear resposta HTTP)
        def send_reaction_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_reaction_to_evolution(message, emoji))
                loop.close()
                logger.info(f"✅ [REACTION] Reação enviada para Evolution API: {request.user.email} {emoji} em {message.id}")
            except Exception as e:
                # Não bloquear se falhar envio (reação já foi salva no banco)
                logger.error(f"⚠️ [REACTION] Erro ao enviar reação para Evolution API (reação salva no banco): {e}", exc_info=True)
        
        # Executar em thread separada para não bloquear resposta HTTP
        import threading
        thread = threading.Thread(target=send_reaction_async, daemon=True)
        thread.start()
        
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
            import asyncio
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
            
            import threading
            thread = threading.Thread(target=remove_reaction_async, daemon=True)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanAccessChat])
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
    def confirm_upload(self, request):
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
        from django.utils import timezone
        from datetime import timedelta
        from apps.chat.utils.s3 import S3Manager
        
        logger = logging.getLogger(__name__)
        
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

