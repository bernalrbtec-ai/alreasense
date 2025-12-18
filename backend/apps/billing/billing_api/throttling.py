"""
Rate limiting para API de Billing
"""
from rest_framework.throttling import BaseThrottle
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BillingAPIRateThrottle(BaseThrottle):
    """
    Rate limit por API Key
    
    Usa config do tenant (api_rate_limit_per_hour)
    """
    
    def allow_request(self, request, view):
        # Pega API Key do auth
        api_key = getattr(request, 'auth', None)
        if not api_key or not hasattr(api_key, 'tenant'):
            return True  # Sem API key, não limita (outro auth vai tratar)
        
        # Busca config do tenant
        config = getattr(api_key.tenant, 'billing_config', None)
        if not config:
            return True  # Sem config, não limita
        
        # Limite por hora (default: 100)
        limit = getattr(config, 'api_rate_limit_per_hour', 100)
        if limit is None or limit == 0:
            return True  # Sem limite
        
        # Cache key
        cache_key = f"billing_ratelimit_{api_key.id}"
        
        # Busca contador por hora
        now = timezone.now()
        hour_key = now.strftime('%Y%m%d%H')
        full_cache_key = f"{cache_key}_{hour_key}"
        
        count = cache.get(full_cache_key, 0)
        
        if count >= limit:
            logger.warning(
                f"⚠️ [BILLING_THROTTLE] Rate limit excedido para API Key {api_key.id} "
                f"({count}/{limit} por hora)"
            )
            return False
        
        # Incrementa
        cache.set(
            full_cache_key,
            count + 1,
            timeout=3600  # 1 hora
        )
        
        logger.debug(
            f"✅ [BILLING_THROTTLE] Request permitida para API Key {api_key.id} "
            f"({count + 1}/{limit} por hora)"
        )
        
        return True
    
    def wait(self):
        """Tempo de espera (em segundos)"""
        return 3600  # 1 hora

