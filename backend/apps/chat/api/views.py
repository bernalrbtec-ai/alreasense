"""
Views para o módulo Flow Chat.
Integra com permissões multi-tenant e departamentos.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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


class ConversationViewSet(DepartmentFilterMixin, viewsets.ModelViewSet):
    """
    ViewSet para conversas.
    
    Filtros automáticos por tenant e departamento conforme permissões do usuário:
    - Admin: vê todas do tenant
    - Gerente/Agente: vê apenas dos seus departamentos
    """
    
    queryset = Conversation.objects.select_related(
        'tenant', 'department', 'assigned_to'
    ).prefetch_related(
        'participants',
        Prefetch(
            'messages',
            queryset=Message.objects.select_related('sender').order_by('-created_at')[:1]
        )
    )
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, CanAccessChat]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'department', 'assigned_to']
    search_fields = ['contact_phone', 'contact_name']
    ordering_fields = ['last_message_at', 'created_at']
    ordering = ['-last_message_at']
    
    def get_serializer_class(self):
        """Usa serializer detalhado no retrieve."""
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer
    
    def perform_create(self, serializer):
        """Associa conversa ao tenant do usuário."""
        serializer.save(
            tenant=self.request.user.tenant,
            assigned_to=self.request.user
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
        Message.objects.create(
            conversation=conversation,
            sender=user,
            content=f"Conversa transferida de {old_department.name} para {conversation.department.name}. Motivo: {reason}",
            direction='outgoing',
            status='sent',
            is_internal=True
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
    
    @action(detail=True, methods=['post'])
    def mark_as_seen(self, request, pk=None):
        """Marca mensagem como vista (incoming)."""
        message = self.get_object()
        
        if message.direction != 'incoming':
            return Response(
                {'error': 'Apenas mensagens recebidas podem ser marcadas como vistas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message.status = 'seen'
        message.save(update_fields=['status'])
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_200_OK
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
        """
        Upload de arquivo para chat.
        Salva localmente e retorna URL.
        """
        file = request.FILES.get('file')
        
        if not file:
            return Response(
                {'error': 'Nenhum arquivo enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validação de tamanho (max 50MB)
        if file.size > 50 * 1024 * 1024:
            return Response(
                {'error': 'Arquivo muito grande (max 50MB)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Salvar localmente
        from apps.chat.utils.storage import save_upload_temporarily
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            file_url = save_upload_temporarily(file, request.user.tenant)
            
            return Response({
                'url': file_url,
                'filename': file.name,
                'size': file.size,
                'mime_type': file.content_type
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"❌ [UPLOAD] Erro ao fazer upload: {e}", exc_info=True)
            return Response(
                {'error': 'Erro ao fazer upload do arquivo'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

