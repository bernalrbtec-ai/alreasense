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
        serializer.save(tenant=self.request.user.tenant)
    
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

