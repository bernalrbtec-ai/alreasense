from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
def campaign_events_debug(request):
    """Endpoint de debug para buscar eventos recentes de campanhas - SEM AUTENTICAÇÃO"""
    logger.info(f"🔍 [EVENTS-DEBUG] Endpoint chamado - Path: {request.path}")
    logger.info(f"🔍 [EVENTS-DEBUG] Headers: {dict(request.headers)}")
    logger.info(f"🔍 [EVENTS-DEBUG] User: {getattr(request, 'user', 'None')}")
    logger.info(f"🔍 [EVENTS-DEBUG] Tenant: {getattr(request, 'tenant', 'None')}")
    
    try:
        # Buscar todas as campanhas ativas (sem filtro de tenant para debug)
        active_campaigns = Campaign.objects.filter(
            status__in=['running', 'paused']
        ).select_related('tenant')
        
        campaigns_status = {}
        
        for campaign in active_campaigns:
            campaigns_status[str(campaign.id)] = {
                'campaign_name': campaign.name,
                'tenant_name': campaign.tenant.name if campaign.tenant else 'Unknown',
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
                'updated_at': campaign.updated_at.isoformat()
            }
        
        logger.info(f"📊 [EVENTS-DEBUG] Encontradas {len(campaigns_status)} campanhas ativas")
        
        return Response({
            'success': True,
            'message': 'Debug endpoint funcionando',
            'campaigns_status': campaigns_status,
            'debug_info': {
                'total_campaigns': len(campaigns_status),
                'timestamp': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"❌ [EVENTS-DEBUG] Erro: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'campaigns_status': {}
        })
