from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Campaign, CampaignContact
from apps.notifications.models import WhatsAppInstance
from .rabbitmq_consumer import get_rabbitmq_consumer
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_campaign_state(request, campaign_id):
    """Debug completo do estado da campanha"""
    tenant = request.tenant
    if not tenant:
        return Response({'error': 'Tenant não encontrado'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        
        # Verificar instâncias WhatsApp
        instances = WhatsAppInstance.objects.filter(tenant=tenant)
        active_instances = instances.filter(is_active=True)
        
        # Verificar contatos da campanha
        contacts = campaign.campaign_contacts.all()
        pending_contacts = contacts.filter(status='pending')
        sending_contacts = contacts.filter(status='sending')
        sent_contacts = contacts.filter(status='sent')
        failed_contacts = contacts.filter(status='failed')
        
        # Verificar RabbitMQ consumer
        consumer = get_rabbitmq_consumer()
        consumer_active = consumer is not None
        campaign_threads = list(consumer.consumer_threads.keys()) if consumer else []
        campaign_running = str(campaign.id) in campaign_threads
        
        debug_info = {
            'campaign': {
                'id': str(campaign.id),
                'name': campaign.name,
                'status': campaign.status,
                'tenant': campaign.tenant.name if campaign.tenant else None,
                'total_contacts': campaign.total_contacts,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            },
            'instances': {
                'total': instances.count(),
                'active': active_instances.count(),
                'active_instances': [
                    {
                        'id': str(inst.id),
                        'name': inst.instance_name,
                        'is_active': inst.is_active,
                        'api_url': inst.api_url,
                        'has_api_key': bool(inst.api_key)
                    }
                    for inst in active_instances
                ]
            },
            'contacts': {
                'total': contacts.count(),
                'pending': pending_contacts.count(),
                'sending': sending_contacts.count(),
                'sent': sent_contacts.count(),
                'failed': failed_contacts.count(),
                'pending_list': [
                    {
                        'id': str(contact.id),
                        'contact_name': contact.contact.name,
                        'contact_phone': contact.contact.phone,
                        'status': contact.status,
                        'created_at': contact.created_at.isoformat()
                    }
                    for contact in pending_contacts[:5]  # Primeiros 5
                ]
            },
            'rabbitmq': {
                'consumer_active': consumer_active,
                'campaign_running': campaign_running,
                'active_threads': campaign_threads,
                'total_threads': len(campaign_threads)
            },
            'auth': {
                'user': request.user.email if request.user else None,
                'tenant': tenant.name if tenant else None,
                'tenant_id': str(tenant.id) if tenant else None
            }
        }
        
        return Response({
            'success': True,
            'debug_info': debug_info
        })
        
    except Campaign.DoesNotExist:
        return Response({'error': 'Campanha não encontrada'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ [DEBUG] Erro no debug da campanha: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
