from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Campaign, CampaignContact
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campaign_retry_info(request, campaign_id):
    """Retorna informações de retry para uma campanha específica"""
    # Tentar obter tenant de múltiplas formas
    tenant = getattr(request, 'tenant', None)
    if not tenant and hasattr(request.user, 'tenant'):
        tenant = request.user.tenant
    
    if not tenant:
        logger.error(f"❌ [RETRY_INFO] Tenant não encontrado - User: {getattr(request.user, 'email', 'anonymous')}")
        return Response({'success': False, 'error': 'Tenant não encontrado'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        campaign = Campaign.objects.get(id=campaign_id, tenant=tenant)
        
        # Verificar se há contato em retry (status 'sending' ou 'failed')
        retry_contact = campaign.campaign_contacts.filter(
            status__in=['sending', 'failed']
        ).select_related('contact').first()
        
        if retry_contact:
            # ✅ CORREÇÃO: Calcular countdown real baseado no tempo até próximo retry
            from django.utils import timezone
            from apps.campaigns.rabbitmq_config import RetryPolicy
            
            # Calcular quando será o próximo retry (baseado em exponential backoff)
            retry_attempt = retry_contact.retry_count or 1
            retry_delay_seconds = RetryPolicy.calculate_delay(retry_attempt)
            
            # Se tem failed_at, calcular tempo restante
            if retry_contact.failed_at:
                next_retry_at = retry_contact.failed_at + timezone.timedelta(seconds=retry_delay_seconds)
                now = timezone.now()
                countdown_seconds = max(0, int((next_retry_at - now).total_seconds()))
            else:
                # Fallback: usar delay calculado
                countdown_seconds = retry_delay_seconds
            
            # Campanha está em retry
            retry_info = {
                'is_retrying': True,
                'retry_contact_name': retry_contact.contact.name,
                'retry_contact_phone': retry_contact.contact.phone,
                'retry_attempt': retry_attempt,
                'retry_error_reason': retry_contact.error_message or 'Erro desconhecido',
                'retry_countdown': countdown_seconds  # ✅ CORREÇÃO: Countdown real calculado
            }
        else:
            # Não há retry ativo
            retry_info = {
                'is_retrying': False,
                'retry_contact_name': None,
                'retry_contact_phone': None,
                'retry_attempt': 0,
                'retry_error_reason': None,
                'retry_countdown': 0
            }
        
        return Response({
            'success': True,
            'retry_info': retry_info
        })
        
    except Campaign.DoesNotExist:
        return Response({'success': False, 'error': 'Campanha não encontrada'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"❌ [RETRY_INFO] Erro ao buscar informações de retry: {e}")
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

