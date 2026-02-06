"""
Rate limiting para endpoints do Gateway IA (teste e reply).
"""
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

# Requisições por minuto
GATEWAY_TEST_RATE = 20
GATEWAY_REPLY_RATE = 60


class _GatewayThrottle(BaseThrottle):
    """Base para throttle por usuário/tenant com cache por minuto."""

    def __init__(self, scope: str, rate_per_minute: int):
        self.scope = scope
        self.rate_per_minute = rate_per_minute

    def get_cache_key(self, request):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return None
        return f"ai_gateway_throttle_{self.scope}_{request.user.id}_{request.user.tenant_id}"

    def allow_request(self, request, view):
        key = self.get_cache_key(request)
        if not key:
            return True
        now = timezone.now()
        minute_bucket = now.strftime("%Y%m%d%H%M")
        full_key = f"{key}_{minute_bucket}"
        count = cache.get(full_key, 0)
        if count >= self.rate_per_minute:
            return False
        cache.set(full_key, count + 1, timeout=70)  # 70s para cobrir o minuto
        return True

    def wait(self):
        return 60  # segundos


class GatewayTestThrottle(_GatewayThrottle):
    """Limite de 20 requisições por minuto por usuário para gateway test."""

    def __init__(self):
        super().__init__("test", GATEWAY_TEST_RATE)


class GatewayReplyThrottle(_GatewayThrottle):
    """Limite de 60 requisições por minuto por usuário para gateway reply (n8n)."""

    def __init__(self):
        super().__init__("reply", GATEWAY_REPLY_RATE)
