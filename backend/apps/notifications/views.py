from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import models

from .models import NotificationTemplate, WhatsAppInstance, NotificationLog
from .serializers import (
    NotificationTemplateSerializer,
    WhatsAppInstanceSerializer,
    NotificationLogSerializer,
    SendNotificationSerializer
)

User = get_user_model()


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for NotificationTemplate."""
    
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin can see all templates
        if user.is_superuser or user.is_staff:
            return NotificationTemplate.objects.all()
        
        # Regular users see only their tenant templates and global templates
        return NotificationTemplate.objects.filter(
            models.Q(tenant=user.tenant) | models.Q(is_global=True)
        )
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test a template with sample context."""
        template = self.get_object()
        context = request.data.get('context', {})
        
        try:
            rendered = template.render(context)
            return Response({
                'success': True,
                'rendered': rendered
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get available template categories."""
        categories = [
            {'value': choice[0], 'label': choice[1]}
            for choice in NotificationTemplate.CATEGORY_CHOICES
        ]
        return Response(categories)


class WhatsAppInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for WhatsAppInstance."""
    
    serializer_class = WhatsAppInstanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin can see all instances
        if user.is_superuser or user.is_staff:
            return WhatsAppInstance.objects.all()
        
        # Regular users see only their tenant instances
        return WhatsAppInstance.objects.filter(tenant=user.tenant)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def check_status(self, request, pk=None):
        """Check instance status."""
        instance = self.get_object()
        instance.check_status()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this instance as default for the tenant."""
        instance = self.get_object()
        
        # Remove default from other instances of same tenant
        WhatsAppInstance.objects.filter(
            tenant=instance.tenant,
            is_default=True
        ).update(is_default=False)
        
        instance.is_default = True
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_test(self, request, pk=None):
        """Send a test message."""
        instance = self.get_object()
        phone = request.data.get('phone')
        message = request.data.get('message', 'Teste de notificação do Alrea Sense')
        
        if not phone:
            return Response({
                'success': False,
                'error': 'Número de telefone obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            import requests
            
            response = requests.post(
                f"{instance.api_url}/message/sendText/{instance.instance_name}",
                headers={'apikey': instance.api_key},
                json={
                    'number': phone,
                    'text': message
                },
                timeout=10
            )
            
            if response.status_code == 200 or response.status_code == 201:
                return Response({
                    'success': True,
                    'message': 'Mensagem de teste enviada com sucesso',
                    'data': response.json()
                })
            else:
                return Response({
                    'success': False,
                    'error': f'Erro ao enviar: {response.text}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for NotificationLog (read-only)."""
    
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Superadmin can see all logs
        if user.is_superuser or user.is_staff:
            return NotificationLog.objects.all()
        
        # Regular users see only their tenant logs
        return NotificationLog.objects.filter(tenant=user.tenant)
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a notification."""
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        template_id = serializer.validated_data['template_id']
        recipient_id = serializer.validated_data['recipient_id']
        context = serializer.validated_data.get('context', {})
        scheduled_at = serializer.validated_data.get('scheduled_at')
        
        try:
            template = NotificationTemplate.objects.get(id=template_id)
            recipient = User.objects.get(id=recipient_id)
            
            # Import task to avoid circular dependency
            from .tasks import send_notification_task
            
            # Queue notification task
            task = send_notification_task.apply_async(
                args=[str(template.id), recipient.id, context],
                eta=scheduled_at
            )
            
            return Response({
                'success': True,
                'message': 'Notificação agendada para envio',
                'task_id': task.id
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get notification statistics."""
        user = request.user
        
        queryset = self.get_queryset()
        
        total = queryset.count()
        sent = queryset.filter(status='sent').count()
        failed = queryset.filter(status='failed').count()
        pending = queryset.filter(status='pending').count()
        
        by_type = {}
        for type_choice in NotificationLog.TYPE_CHOICES:
            type_code = type_choice[0]
            by_type[type_code] = queryset.filter(type=type_code).count()
        
        return Response({
            'total': total,
            'sent': sent,
            'failed': failed,
            'pending': pending,
            'by_type': by_type
        })

