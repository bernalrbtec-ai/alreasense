from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404
from .models import Campaign, CampaignMessage, CampaignContact, CampaignLog, CampaignNotification
from .serializers import (
    CampaignSerializer, CampaignContactSerializer,
    CampaignLogSerializer, CampaignStatsSerializer,
    CampaignNotificationSerializer, NotificationMarkReadSerializer,
    NotificationReplySerializer
)


class CampaignViewSet(viewsets.ModelViewSet):
    """API para gerenciamento de campanhas"""
    
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar por tenant"""
        user = self.request.user
        if user.is_superuser and not user.tenant:
            return Campaign.objects.none()  # Superadmin não vê campanhas individuais
        return Campaign.objects.filter(tenant=user.tenant).prefetch_related('instances', 'messages')
    
    def perform_create(self, serializer):
        """Criar campanha associada ao tenant e usuário"""
        # Passar tag_id, state_ids e contact_ids para o serializer via context
        tag_id = self.request.data.get('tag_id')
        contact_ids = self.request.data.get('contact_ids', [])
        
        serializer.context['tag_id'] = tag_id
        serializer.context['contact_ids'] = contact_ids
        
        print(f"📊 Criando campanha:")
        print(f"   Tag ID: {tag_id}")
        print(f"   Contact IDs: {contact_ids}")
        
        campaign = serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
        
        # Log de criação
        CampaignLog.log_campaign_created(campaign, self.request.user)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Iniciar campanha"""
        campaign = self.get_object()
        
        if campaign.status != 'draft' and campaign.status != 'scheduled':
            return Response(
                {'error': 'Campanha não pode ser iniciada neste status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campaign.start()
        CampaignLog.log_campaign_started(campaign, request.user)
        
        # Disparar task Celery para processar campanha
        from .tasks import process_campaign
        process_campaign.delay(str(campaign.id))
        
        return Response({
            'message': 'Campanha iniciada com sucesso',
            'status': 'running'
        })
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pausar campanha"""
        campaign = self.get_object()
        
        print(f"🛑 PAUSANDO CAMPANHA: {campaign.name} (ID: {campaign.id})")
        print(f"   Status atual: {campaign.status}")
        
        campaign.pause()
        
        # Verificar se foi pausada
        campaign.refresh_from_db()
        print(f"   Status após pausar: {campaign.status}")
        
        # Log de pausa
        CampaignLog.log_campaign_paused(campaign, request.user)
        
        return Response({
            'message': 'Campanha pausada com sucesso',
            'status': campaign.status
        })
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Retomar campanha"""
        campaign = self.get_object()
        campaign.resume()
        
        # Log de retomada
        CampaignLog.log_campaign_resumed(campaign, request.user)
        
        # Disparar task Celery novamente para continuar processamento
        from .tasks import process_campaign
        process_campaign.delay(str(campaign.id))
        
        return Response({
            'message': 'Campanha retomada com sucesso',
            'status': 'running'
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancelar campanha"""
        campaign = self.get_object()
        campaign.cancel()
        return Response({'message': 'Campanha cancelada'})
    
    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Listar contatos da campanha"""
        campaign = self.get_object()
        contacts = CampaignContact.objects.filter(campaign=campaign)
        
        # Filtros opcionais
        status_filter = request.query_params.get('status')
        if status_filter:
            contacts = contacts.filter(status=status_filter)
        
        serializer = CampaignContactSerializer(contacts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Listar logs da campanha"""
        campaign = self.get_object()
        logs = CampaignLog.objects.filter(campaign=campaign)
        
        # Filtros opcionais
        log_type = request.query_params.get('log_type')
        severity = request.query_params.get('severity')
        
        if log_type:
            logs = logs.filter(log_type=log_type)
        if severity:
            logs = logs.filter(severity=severity)
        
        # Paginação
        limit = int(request.query_params.get('limit', 100))
        logs = logs[:limit]
        
        serializer = CampaignLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Estatísticas gerais de campanhas"""
        tenant = request.user.tenant
        campaigns = Campaign.objects.filter(tenant=tenant)
        
        stats = {
            'total_campaigns': campaigns.count(),
            'active_campaigns': campaigns.filter(status='running').count(),
            'completed_campaigns': campaigns.filter(status='completed').count(),
            'total_messages_sent': campaigns.aggregate(total=Count('messages_sent'))['total'] or 0,
            'total_messages_delivered': campaigns.aggregate(total=Count('messages_delivered'))['total'] or 0,
            'avg_success_rate': campaigns.aggregate(avg=Avg('messages_delivered'))['avg'] or 0,
            'campaigns_by_status': dict(campaigns.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        }
        
        serializer = CampaignStatsSerializer(stats)
        return Response(serializer.data)


class CampaignNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """API para notificações de campanhas"""
    
    serializer_class = CampaignNotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar por tenant e ordenar por mais recentes"""
        return CampaignNotification.objects.filter(
            tenant=self.request.user.tenant
        ).select_related(
            'campaign', 'contact', 'instance', 'sent_by'
        ).order_by('-created_at')
    
    def get_serializer_context(self):
        """Adicionar request ao contexto"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Contar notificações não lidas"""
        count = self.get_queryset().filter(status='unread').count()
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['post'])
    def mark_as_read(self, request):
        """Marcar notificação como lida"""
        serializer = NotificationMarkReadSerializer(data=request.data)
        if serializer.is_valid():
            notification_id = serializer.validated_data['notification_id']
            
            try:
                notification = get_object_or_404(
                    CampaignNotification,
                    id=notification_id,
                    tenant=request.user.tenant
                )
                
                notification.mark_as_read(user=request.user)
                
                return Response({
                    'message': 'Notificação marcada como lida',
                    'notification_id': str(notification_id)
                })
                
            except Exception as e:
                return Response(
                    {'error': f'Erro ao marcar notificação: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def reply(self, request):
        """Responder notificação"""
        serializer = NotificationReplySerializer(data=request.data)
        if serializer.is_valid():
            notification_id = serializer.validated_data['notification_id']
            message = serializer.validated_data['message']
            
            try:
                notification = get_object_or_404(
                    CampaignNotification,
                    id=notification_id,
                    tenant=request.user.tenant
                )
                
                # TODO: Implementar envio via Evolution API
                # Por enquanto, apenas marcar como respondida
                notification.mark_as_replied(message, request.user)
                
                return Response({
                    'message': 'Resposta enviada com sucesso',
                    'notification_id': str(notification_id)
                })
                
            except Exception as e:
                return Response(
                    {'error': f'Erro ao enviar resposta: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Marcar todas as notificações como lidas"""
        try:
            notifications = self.get_queryset().filter(status='unread')
            count = notifications.count()
            
            for notification in notifications:
                notification.mark_as_read(user=request.user)
            
            return Response({
                'message': f'{count} notificações marcadas como lidas'
            })
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao marcar notificações: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

