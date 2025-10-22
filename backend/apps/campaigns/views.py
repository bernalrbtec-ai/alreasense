from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Campaign, CampaignMessage, CampaignContact, CampaignLog, CampaignNotification
# CampaignNotification reativado
from .serializers import (
    CampaignSerializer, CampaignContactSerializer,
    CampaignLogSerializer, CampaignStatsSerializer,
    CampaignNotificationSerializer, NotificationMarkReadSerializer, NotificationReplySerializer
)


class CampaignViewSet(viewsets.ModelViewSet):
    """API para gerenciamento de campanhas"""
    
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filtrar por tenant e status"""
        user = self.request.user
        if user.is_superuser and not user.tenant:
            return Campaign.objects.none()  # Superadmin não vê campanhas individuais
        
        queryset = Campaign.objects.filter(tenant=user.tenant).prefetch_related('instances', 'messages')
        
        # Suporte a filtro de status: ?status=active,paused
        status_param = self.request.query_params.get('status')
        if status_param:
            status_list = [s.strip() for s in status_param.split(',')]
            queryset = queryset.filter(status__in=status_list)
        else:
            # Por padrão, excluir campanhas 'stopped' da lista principal
            # Para ver campanhas stopped, usar ?status=stopped explicitamente
            queryset = queryset.exclude(status='stopped')
        
        return queryset
    
    def perform_create(self, serializer):
        """Criar campanha associada ao tenant e usuário"""
        # Passar tag_id, state_ids e contact_ids para o serializer via context
        tag_id = self.request.data.get('tag_id')
        contact_ids = self.request.data.get('contact_ids', [])
        
        serializer.context['tag_id'] = tag_id
        serializer.context['contact_ids'] = contact_ids
        
        
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
        
        # Iniciar processamento via RabbitMQ Consumer
        try:
            from .rabbitmq_consumer import get_rabbitmq_consumer
            consumer = get_rabbitmq_consumer()
            if consumer:
                success = consumer.start_campaign(str(campaign.id))
                if not success:
                    logger.error(f"❌ [VIEW] Falha ao iniciar campanha {campaign.name} no RabbitMQ")
            else:
                logger.error("❌ [VIEW] RabbitMQ Consumer não disponível")
        except Exception as e:
            logger.error(f"❌ [VIEW] Erro ao iniciar campanha via RabbitMQ: {e}")
        
        return Response({
            'message': 'Campanha iniciada com sucesso',
            'status': 'running'
        })
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pausar campanha"""
        campaign = self.get_object()
        
        
        campaign.pause()
        
        # Verificar se foi pausada
        campaign.refresh_from_db()
        
        # Log de pausa
        CampaignLog.log_campaign_paused(campaign, request.user)
        
        return Response({
            'message': 'Campanha pausada com sucesso',
            'status': campaign.status
        })
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Retomar campanha"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            campaign = self.get_object()
            logger.info(f"🔄 Tentando retomar campanha: {campaign.name} (ID: {campaign.id})")
            logger.info(f"📊 Status atual: {campaign.status}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar campanha {pk}: {str(e)}")
            return Response({
                'error': f'Campanha não encontrada: {str(e)}',
                'success': False
            }, status=404)
        
        try:
            # Resumir campanha
            campaign.resume()
            
            # Log de retomada
            CampaignLog.log_campaign_resumed(campaign, request.user)
            
            # 🚀 REINICIAR CONSUMER RABBITMQ para continuar processamento
            from .rabbitmq_consumer import get_rabbitmq_consumer
            consumer = get_rabbitmq_consumer()
            if consumer:
                consumer.resume_campaign(str(campaign.id))
                logger.info(f"✅ [RESUME] Consumer reiniciado para campanha {campaign.name}")
            else:
                logger.warning(f"⚠️ [RESUME] Consumer RabbitMQ não disponível")
            
            return Response({
                'message': f'Campanha "{campaign.name}" retomada com sucesso',
                'status': campaign.status,
                'success': True
            })
            
        except Exception as e:
            # Se falhar, ainda assim marcar como running
            campaign.resume()  # Garantir que está running
            CampaignLog.log_campaign_resumed(campaign, request.user)
            
            # Tentar reiniciar consumer mesmo com erro
            try:
                from .rabbitmq_consumer import get_rabbitmq_consumer
                consumer = get_rabbitmq_consumer()
                if consumer:
                    consumer.resume_campaign(str(campaign.id))
            except Exception as consumer_error:
                logger.error(f"❌ [RESUME] Erro ao reiniciar consumer: {consumer_error}")
            
            # Log do erro
            CampaignLog.objects.create(
                campaign=campaign,
                log_type='error',
                severity='warning',
                message=f'Campanha retomada, mas houve erro: {str(e)}',
                details={'error': str(e), 'campaign_id': str(campaign.id)}
            )
            
            return Response({
                'message': 'Campanha retomada com sucesso',
                'status': campaign.status,
                'warning': f'Task Celery falhou: {str(e)}',
                'success': True
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
    pagination_class = None  # Desabilitar paginação para simplificar
    
    def get_queryset(self):
        """Filtrar por tenant e ordenar por mais recentes"""
        queryset = CampaignNotification.objects.filter(
            tenant=self.request.user.tenant
        ).select_related(
            'campaign', 'contact', 'instance', 'sent_by'
        )
        
        # Filtros opcionais
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
            
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
            
        # Ordenação
        order_by = self.request.query_params.get('order_by', '-created_at')
        queryset = queryset.order_by(order_by)
        
        return queryset
    
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
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Estatísticas de notificações"""
        queryset = self.get_queryset()
        
        stats = {
            'total': queryset.count(),
            'unread': queryset.filter(status='unread').count(),
            'read': queryset.filter(status='read').count(),
            'replied': queryset.filter(status='replied').count(),
            'by_type': {
                'response': queryset.filter(notification_type='response').count(),
                'delivery': queryset.filter(notification_type='delivery').count(),
                'read': queryset.filter(notification_type='read').count(),
            },
            'recent_activity': queryset.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
        }
        
        return Response(stats)
    
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
                
                # Enviar resposta via Evolution API
                success = self.send_reply_via_evolution(notification, message)
                
                if success:
                    notification.mark_as_replied(message, request.user)
                else:
                    notification.mark_as_failed(request.user, 'Erro ao enviar via Evolution API')
                    return Response(
                        {'error': 'Erro ao enviar mensagem via WhatsApp'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
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
    
    def send_reply_via_evolution(self, notification, message):
        """Enviar resposta via Evolution API"""
        try:
            import requests
            from apps.connections.models import EvolutionConnection
            
            # notification.instance já é WhatsAppInstance
            wa_instance = notification.instance
            
            if not wa_instance or not wa_instance.is_active:
                return False
            
            # Buscar servidor Evolution para fallback de configs
            evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
            if not evolution_server:
                return False
            
            # Preparar dados para envio
            payload = {
                "number": notification.contact.phone,
                "text": message
            }
            
            # Usar config da instância ou fallback do servidor
            api_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
            api_key = wa_instance.api_key or evolution_server.api_key
            instance_name = wa_instance.instance_name  # UUID da instância
            
            headers = {
                "Content-Type": "application/json",
                "apikey": api_key
            }
            
            # URL da Evolution API com UUID correto
            url = f"{api_url}/message/sendText/{instance_name}"
            
            # Fazer requisição
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return True
            else:
                return False
                
        except Exception as e:
            return False

