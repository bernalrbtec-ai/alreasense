"""
Views v2 - Sistema de Campanhas com RabbitMQ
Implementa controle robusto de campanhas com auto-recovery
"""
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Campaign, CampaignContact, CampaignLog
from .rabbitmq_consumer import get_rabbitmq_consumer
from .monitor import campaign_health_monitor, system_health_monitor
from .serializers import CampaignSerializer, CampaignDetailSerializer


class CampaignControlView(generics.GenericAPIView):
    """
    Controle de campanhas com novo sistema
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, campaign_id, action):
        """
        Controla uma campanha (start, pause, resume, stop)
        """
        try:
            campaign = get_object_or_404(Campaign, id=campaign_id, tenant=request.user.tenant)
            
            if action == 'start':
                # Iniciar campanha
                if campaign.status != 'draft':
                    return Response(
                        {'error': 'Apenas campanhas em rascunho podem ser iniciadas'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validar se tem contatos
                pending_contacts = CampaignContact.objects.filter(
                    campaign=campaign,
                    status__in=['pending', 'sending']
                ).count()
                
                if pending_contacts == 0:
                    return Response(
                        {'error': 'Campanha não possui contatos para envio'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Iniciar campanha
                consumer = get_rabbitmq_consumer()
                success = consumer.start_campaign(str(campaign.id)) if consumer else False
                
                if success:
                    return Response({
                        'message': f'Campanha {campaign.name} iniciada com sucesso',
                        'campaign_id': str(campaign.id)
                    })
                else:
                    return Response(
                        {'error': 'Erro ao iniciar campanha'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            elif action == 'pause':
                # Pausar campanha
                if campaign.status != 'running':
                    return Response(
                        {'error': 'Apenas campanhas em execução podem ser pausadas'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                consumer = get_rabbitmq_consumer()
                if consumer:
                    consumer.pause_campaign(str(campaign.id))
                
                return Response({
                    'message': f'Campanha {campaign.name} pausada com sucesso'
                })
            
            elif action == 'resume':
                # Resumir campanha
                if campaign.status != 'paused':
                    return Response(
                        {'error': 'Apenas campanhas pausadas podem ser resumidas'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                consumer = get_rabbitmq_consumer()
                if consumer:
                    consumer.resume_campaign(str(campaign.id))
                
                return Response({
                    'message': f'Campanha {campaign.name} resumida com sucesso'
                })
            
            elif action == 'stop':
                # Parar campanha
                if campaign.status not in ['running', 'paused']:
                    return Response(
                        {'error': 'Apenas campanhas em execução ou pausadas podem ser paradas'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                consumer = get_rabbitmq_consumer()
                if consumer:
                    consumer.stop_campaign(str(campaign.id))
                
                return Response({
                    'message': f'Campanha {campaign.name} parada com sucesso'
                })
            
            else:
                return Response(
                    {'error': 'Ação inválida. Use: start, pause, resume, stop'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            return Response(
                {'error': f'Erro ao controlar campanha: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_health(request, campaign_id):
    """
    Retorna saúde de uma campanha específica
    """
    try:
        campaign = get_object_or_404(Campaign, id=campaign_id, tenant=request.user.tenant)
        
        # Obter métricas de saúde
        health_metrics = campaign_health_monitor.get_campaign_health(str(campaign.id))
        
        if not health_metrics:
            return Response(
                {'error': 'Não foi possível obter métricas de saúde'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Obter alertas ativos
        alerts = campaign_health_monitor.get_campaign_alerts(str(campaign.id))
        
        # Status do consumer
        consumer = get_rabbitmq_consumer()
        consumer_status = consumer.get_campaign_status(str(campaign.id)) if consumer else {'status': 'not_available'}
        
        return Response({
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.name,
            'health_metrics': health_metrics.to_dict(),
            'alerts': [alert.to_dict() for alert in alerts if not alert.resolved],
            'consumer_status': consumer_status,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter saúde da campanha: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """
    Retorna saúde geral do sistema
    """
    try:
        system_metrics = system_health_monitor.get_system_health()
        
        return Response({
            'system_health': system_metrics,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter saúde do sistema: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_campaigns(request):
    """
    Lista campanhas ativas com status do engine
    """
    try:
        # Campanhas do tenant
        tenant_campaigns = Campaign.objects.filter(tenant=request.user.tenant)
        
        # Campanhas ativas no consumer
        active_consumer_campaigns = rabbitmq_consumer.get_active_campaigns()
        
        campaigns_data = []
        for campaign in tenant_campaigns:
            campaign_data = {
                'id': str(campaign.id),
                'name': campaign.name,
                'status': campaign.status,
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_failed': campaign.messages_failed,
                'is_consumer_active': str(campaign.id) in active_consumer_campaigns,
                'consumer_status': rabbitmq_consumer.get_campaign_status(str(campaign.id))
            }
            
            # Adicionar métricas de saúde se disponível
            if campaign.status == 'running':
                health_metrics = campaign_health_monitor.get_campaign_health(str(campaign.id))
                if health_metrics:
                    campaign_data['health_score'] = health_metrics.health_score
                    campaign_data['processing_rate'] = health_metrics.processing_rate
                    campaign_data['issues'] = health_metrics.issues
            
            campaigns_data.append(campaign_data)
        
        return Response({
            'campaigns': campaigns_data,
            'active_consumers': len(active_consumer_campaigns),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao listar campanhas: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_alert(request, campaign_id, alert_id):
    """
    Resolve um alerta específico
    """
    try:
        campaign = get_object_or_404(Campaign, id=campaign_id, tenant=request.user.tenant)
        
        campaign_health_monitor.resolve_alert(str(campaign.id), alert_id)
        
        return Response({
            'message': f'Alerta {alert_id} resolvido com sucesso'
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao resolver alerta: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_metrics(request, campaign_id):
    """
    Retorna métricas detalhadas de uma campanha
    """
    try:
        campaign = get_object_or_404(Campaign, id=campaign_id, tenant=request.user.tenant)
        
        # Métricas básicas
        pending_contacts = CampaignContact.objects.filter(
            campaign=campaign,
            status__in=['pending', 'sending']
        ).count()
        
        sent_contacts = CampaignContact.objects.filter(
            campaign=campaign,
            status='sent'
        ).count()
        
        failed_contacts = CampaignContact.objects.filter(
            campaign=campaign,
            status='failed'
        ).count()
        
        delivered_contacts = CampaignContact.objects.filter(
            campaign=campaign,
            status='delivered'
        ).count()
        
        # Histórico de logs
        recent_logs = CampaignLog.objects.filter(
            campaign=campaign
        ).order_by('-created_at')[:10]
        
        logs_data = []
        for log in recent_logs:
            logs_data.append({
                'timestamp': log.created_at.isoformat(),
                'type': log.log_type,
                'severity': log.severity,
                'message': log.message,
                'details': log.details
            })
        
        # Métricas de saúde
        health_metrics = campaign_health_monitor.get_campaign_health(str(campaign.id))
        
        return Response({
            'campaign_id': str(campaign.id),
            'campaign_name': campaign.name,
            'status': campaign.status,
            'contacts': {
                'pending': pending_contacts,
                'sent': sent_contacts,
                'delivered': delivered_contacts,
                'failed': failed_contacts,
                'total': pending_contacts + sent_contacts + delivered_contacts + failed_contacts
            },
            'messages': {
                'sent': campaign.messages_sent,
                'delivered': campaign.messages_delivered,
                'failed': campaign.messages_failed
            },
            'health_metrics': health_metrics.to_dict() if health_metrics else None,
            'recent_logs': logs_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter métricas: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
