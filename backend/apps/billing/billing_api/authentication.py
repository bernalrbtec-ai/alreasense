"""
Autenticação por API Key para Billing API
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from apps.billing.billing_api import BillingAPIKey
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BillingAPIKeyAuthentication(BaseAuthentication):
    """
    Autenticação via API Key no header X-Billing-API-Key
    
    Retorna (None, api_key_obj) onde api_key_obj tem:
    - tenant: Tenant associado
    - config: billing_config do tenant
    """
    
    def authenticate(self, request):
        api_key = request.headers.get('X-Billing-API-Key') or request.headers.get('X-API-Key')
        
        if not api_key:
            return None  # Deixa outros authenticators tentarem
        
        try:
            key_obj = BillingAPIKey.objects.select_related(
                'tenant',
                'tenant__billing_config'
            ).get(key=api_key)
            
            # Valida key
            ip_address = self._get_client_ip(request)
            is_valid, reason = key_obj.is_valid(ip_address)
            
            if not is_valid:
                logger.warning(
                    f"⚠️ [BILLING_AUTH] API Key inválida: {reason} "
                    f"(key_id: {key_obj.id}, IP: {ip_address})"
                )
                raise AuthenticationFailed(reason)
            
            # Verifica se API está habilitada para o tenant
            if not key_obj.tenant.billing_config.api_enabled:
                logger.warning(
                    f"⚠️ [BILLING_AUTH] API desabilitada para tenant {key_obj.tenant.name}"
                )
                raise AuthenticationFailed("API de Billing não habilitada para este tenant")
            
            # Incrementa uso
            key_obj.increment_usage(ip_address)
            
            logger.info(
                f"✅ [BILLING_AUTH] Autenticação bem-sucedida "
                f"(key_id: {key_obj.id}, tenant: {key_obj.tenant.name}, IP: {ip_address})"
            )
            
            # Retorna (None, key_obj) - user é None, auth é key_obj
            return (None, key_obj)
        
        except BillingAPIKey.DoesNotExist:
            logger.warning(f"⚠️ [BILLING_AUTH] API Key não encontrada")
            raise AuthenticationFailed('API Key inválida')
        except Exception as e:
            logger.error(f"❌ [BILLING_AUTH] Erro na autenticação: {e}", exc_info=True)
            raise AuthenticationFailed('Erro ao autenticar')
    
    def _get_client_ip(self, request):
        """Extrai IP do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

