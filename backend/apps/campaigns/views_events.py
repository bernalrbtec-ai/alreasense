from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_events(request):
    """Endpoint para buscar eventos recentes de campanhas"""
    try:
        tenant = request.tenant
        
        # Buscar logs de campanhas dos últimos 5 minutos
        since = timezone.now() - timedelta(minutes=5)
        
        # Buscar logs de campanha recentes
        recent_logs = CampaignLog.objects.filter(
            campaign__tenant=tenant,
            created_at__gte=since
        ).order_by('-created_at')[:50]
        
        events = []
        for log in recent_logs:
            event = {
                'id': str(log.id),
                'campaign_id': str(log.campaign.id),
                'campaign_name': log.campaign.name,
                'event_type': log.event_type,
                'message': log.message,
                'created_at': log.created_at.isoformat(),
                'campaign_status': log.campaign.status,
                'campaign_data': {
                    'messages_sent': log.campaign.messages_sent,
                    'messages_delivered': log.campaign.messages_delivered,
                    'messages_read': log.campaign.messages_read,
                    'messages_failed': log.campaign.messages_failed,
                    'total_contacts': log.campaign.total_contacts,
                    'progress_percentage': (log.campaign.messages_sent / log.campaign.total_contacts * 100) if log.campaign.total_contacts > 0 else 0,
                    'last_message_sent_at': log.campaign.last_message_sent_at.isoformat() if log.campaign.last_message_sent_at else None,
                    'next_message_scheduled_at': log.campaign.next_message_scheduled_at.isoformat() if log.campaign.next_message_scheduled_at else None,
                    'next_contact_name': log.campaign.next_contact_name,
                    'next_contact_phone': log.campaign.next_contact_phone,
                    'last_contact_name': log.campaign.last_contact_name,
                    'last_contact_phone': log.campaign.last_contact_phone,
                }
            }
            events.append(event)
        
        # Buscar campanhas ativas para verificar status
        active_campaigns = Campaign.objects.filter(
            tenant=tenant,
            status='running'
        ).values(
            'id', 'name', 'status', 'messages_sent', 'messages_delivered', 
            'messages_read', 'messages_failed', 'total_contacts',
            'last_message_sent_at', 'next_message_scheduled_at',
            'next_contact_name', 'next_contact_phone',
            'last_contact_name', 'last_contact_phone', 'updated_at'
        )
        
        # Converter para dict para facilitar uso no frontend
        campaigns_status = {str(c['id']): c for c in active_campaigns}
        
        return Response({
            'success': True,
            'events': events,
            'campaigns_status': campaigns_status,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ [EVENTS] Erro ao buscar eventos: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_realtime_status(request, campaign_id):
    """Endpoint para status em tempo real de uma campanha específica"""
    try:
        tenant = request.tenant
        
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        
        # Calcular tempo restante para próxima mensagem
        time_remaining = None
        if campaign.next_message_scheduled_at and campaign.status == 'running':
            now = timezone.now()
            if campaign.next_message_scheduled_at > now:
                delta = campaign.next_message_scheduled_at - now
                time_remaining = int(delta.total_seconds())
            else:
                time_remaining = 0
        
        # Buscar último log da campanha
        last_log = CampaignLog.objects.filter(campaign=campaign).order_by('-created_at').first()
        
        return Response({
            'success': True,
            'campaign': {
                'id': str(campaign.id),
                'name': campaign.name,
                'status': campaign.status,
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_read': campaign.messages_read,
                'messages_failed': campaign.messages_failed,
                'total_contacts': campaign.total_contacts,
                'progress_percentage': (campaign.messages_sent / campaign.total_contacts * 100) if campaign.total_contacts > 0 else 0,
                'last_message_sent_at': campaign.last_message_sent_at.isoformat() if campaign.last_message_sent_at else None,
                'next_message_scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                'next_contact_name': campaign.next_contact_name,
                'next_contact_phone': campaign.next_contact_phone,
                'last_contact_name': campaign.last_contact_name,
                'last_contact_phone': campaign.last_contact_phone,
                'time_remaining_seconds': time_remaining,
                'last_log': {
                    'event_type': last_log.event_type if last_log else None,
                    'message': last_log.message if last_log else None,
                    'created_at': last_log.created_at.isoformat() if last_log else None
                },
                'updated_at': campaign.updated_at.isoformat()
            }
        })
        
    except Campaign.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Campanha não encontrada'
        }, status=404)
    except Exception as e:
        logger.error(f"❌ [STATUS] Erro ao buscar status da campanha {campaign_id}: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
