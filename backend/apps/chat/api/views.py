"""
Views para o módulo Flow Chat.
Integra com permissões multi-tenant e departamentos.
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch

from apps.chat.models import Conversation, Message, MessageAttachment
from apps.chat.api.serializers import (
    ConversationSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    MessageAttachmentSerializer
)
from apps.authn.permissions import CanAccessChat
from apps.authn.mixins import DepartmentFilterMixin
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

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
        """
        queryset = super().get_queryset()
        user = self.request.user
        
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
                
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        endpoint,
                        params={'groupJid': group_jid},
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        group_info = response.json()
                        
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
                        return Response(
                            {'error': f'Erro ao buscar grupo: {response.status_code}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
            
            # 👤 CONTATOS INDIVIDUAIS: Endpoint /chat/fetchProfilePictureUrl
            else:
                clean_phone = conversation.contact_phone.replace('+', '').replace('@s.whatsapp.net', '')
                endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance_name}"
                
                logger.info(f"🔄 [REFRESH CONTATO] Buscando foto do contato {clean_phone}")
                
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(
                        endpoint,
                        params={'number': clean_phone},
                        headers=headers
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
                    else:
                        logger.warning(f"⚠️ [REFRESH CONTATO] Erro API: {response.status_code}")
            
            # Salvar alterações
            if update_fields:
                conversation.save(update_fields=update_fields)
                logger.info(f"✅ [REFRESH] {len(update_fields)} campos atualizados")
            
            # Salvar no cache por 5min
            cache.set(cache_key, True, 300)
            
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
            return Response(
                {'error': 'Timeout ao buscar informações'},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as e:
            logger.error(f"❌ [REFRESH] Erro: {e}", exc_info=True)
            return Response(
                {'error': f'Erro interno: {str(e)}'},
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
        
        # Verificar se já existe conversa
        existing = Conversation.objects.filter(
            tenant=request.user.tenant,
            contact_phone=contact_phone
        ).first()
        
        if existing:
            return Response(
                {
                    'message': 'Conversa já existe',
                    'conversation': ConversationSerializer(existing).data
                },
                status=status.HTTP_200_OK
            )
        
        # Criar nova conversa
        conversation = Conversation.objects.create(
            tenant=request.user.tenant,
            department=department,
            contact_phone=contact_phone,
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
        """Fecha uma conversa."""
        conversation = self.get_object()
        conversation.status = 'closed'
        conversation.save(update_fields=['status'])
        
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
        """
        from apps.chat.webhooks import send_read_receipt
        
        conversation = self.get_object()
        
        # Buscar mensagens recebidas (direction='incoming') que ainda não foram marcadas como lidas
        unread_messages = Message.objects.filter(
            conversation=conversation,
            direction='incoming',
            status__in=['sent', 'delivered']  # Ainda não lidas
        ).order_by('-created_at')
        
        marked_count = 0
        for message in unread_messages:
            # Enviar confirmação de leitura para Evolution API
            send_read_receipt(conversation, message)
            
            # Atualizar status local
            message.status = 'seen'
            message.save(update_fields=['status'])
            marked_count += 1
        
        # ✅ CORREÇÃO: Broadcast conversation_updated para atualizar lista em tempo real
        if marked_count > 0:
            from apps.chat.utils.websocket import broadcast_conversation_updated
            
            broadcast_conversation_updated(conversation)
            logger.info(f"📡 [WEBSOCKET] {marked_count} mensagens marcadas como lidas, broadcast enviado")
        
        return Response(
            {
                'success': True,
                'marked_count': marked_count,
                'message': f'{marked_count} mensagens marcadas como lidas'
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
        Lista mensagens de uma conversa específica.
        GET /conversations/{id}/messages/
        """
        conversation = self.get_object()
        messages = Message.objects.filter(
            conversation=conversation
        ).select_related('sender').prefetch_related('attachments').order_by('created_at')
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
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
        
        conversation.save()
        
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
        
        # Broadcast via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'conversation_transferred',
                'conversation_id': str(conversation.id),
                'new_agent': conversation.assigned_to.email if conversation.assigned_to else None,
                'new_department': conversation.department.name,
                'transferred_by': user.email
            }
        )
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"✅ [TRANSFER] Conversa {conversation.id} transferida por {user.email} "
            f"para {conversation.department.name}"
        )
        
        return Response(
            ConversationSerializer(conversation).data,
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
        """Filtra mensagens por conversas acessíveis ao usuário."""
        user = self.request.user
        
        if user.is_superuser:
            return self.queryset
        
        if user.is_admin:
            return self.queryset.filter(conversation__tenant=user.tenant)
        
        # Gerente/Agente: apenas mensagens de conversas dos seus departamentos
        user_departments = user.departments.all()
        if not user_departments.exists():
            return self.queryset.none()
        
        return self.queryset.filter(
            conversation__tenant=user.tenant,
            conversation__department__in=user_departments
        )
    
    def perform_create(self, serializer):
        """
        Cria mensagem e envia para RabbitMQ para processamento assíncrono.
        """
        message = serializer.save()
        
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

