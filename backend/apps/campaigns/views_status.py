from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from apps.campaigns.models import Campaign
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_status(request):
    """Endpoint simples para status de campanhas ativas com dados do delay"""
    try:
        tenant = request.tenant
        
        # Buscar apenas campanhas ativas
        active_campaigns = Campaign.objects.filter(
            tenant=tenant,
            status='running'
        ).select_related('tenant')
        
        campaigns_data = []
        for campaign in active_campaigns:
            # Calcular tempo restante para próxima mensagem
            time_remaining = None
            if campaign.next_message_scheduled_at and campaign.status == 'running':
                now = timezone.now()
                if campaign.next_message_scheduled_at > now:
                    delta = campaign.next_message_scheduled_at - now
                    time_remaining = int(delta.total_seconds())
                else:
                    time_remaining = 0
            
            campaign_data = {
                'id': str(campaign.id),
                'name': campaign.name,
                'status': campaign.status,
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_read': campaign.messages_read,
                'messages_failed': campaign.messages_failed,
                'total_contacts': campaign.total_contacts,
                'progress_percentage': ((campaign.messages_sent + campaign.messages_failed) / campaign.total_contacts * 100) if campaign.total_contacts > 0 else 0,
                'last_message_sent_at': campaign.last_message_sent_at.isoformat() if campaign.last_message_sent_at else None,
                'next_message_scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                'next_contact_name': campaign.next_contact_name,
                'next_contact_phone': campaign.next_contact_phone,
                'last_contact_name': campaign.last_contact_name,
                'last_contact_phone': campaign.last_contact_phone,
                'time_remaining_seconds': time_remaining,
                'updated_at': campaign.updated_at.isoformat()
            }
            campaigns_data.append(campaign_data)
        
        return Response({
            'success': True,
            'campaigns': campaigns_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ [STATUS] Erro ao buscar status: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
