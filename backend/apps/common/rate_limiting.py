"""
Rate limiting utilities for API endpoints.
Uses Redis for distributed rate limiting.
"""
import logging
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exceção para rate limit excedido."""
    pass


def rate_limit(key_func, rate='10/m', method='ALL'):
    """
    Decorator para rate limiting de views.
    
    Args:
        key_func: Função que retorna a chave única para o rate limit (ex: IP, user_id)
        rate: Taxa no formato "count/period" (ex: "10/m", "100/h", "1000/d")
        method: Método HTTP para aplicar o rate limit ('GET', 'POST', 'ALL')
    
    Exemplo:
        @rate_limit(key_func=lambda req: req.META.get('REMOTE_ADDR'), rate='10/m')
        def my_view(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Skip rate limiting in DEBUG mode (opcional)
            if settings.DEBUG and not getattr(settings, 'RATELIMIT_ENABLE_IN_DEBUG', False):
                return view_func(request, *args, **kwargs)
            
            # Verificar método HTTP
            if method != 'ALL' and request.method != method:
                return view_func(request, *args, **kwargs)
            
            # Obter chave única
            try:
                rate_key = key_func(request)
                if not rate_key:
                    # Se não conseguir chave, permitir acesso
                    logger.warning("Rate limit: Unable to get key, allowing request")
                    return view_func(request, *args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limit: Error getting key: {e}")
                return view_func(request, *args, **kwargs)
            
            # Parse rate (ex: "10/m" -> 10 requests per minute)
            count, period = rate.split('/')
            count = int(count)
            
            period_seconds = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400,
            }.get(period, 60)
            
            # Cache key
            cache_key = f"rate_limit:{view_func.__name__}:{rate_key}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Check limit
            if current_count >= count:
                logger.warning(
                    f"Rate limit exceeded for {view_func.__name__}",
                    extra={
                        'key': rate_key,
                        'count': current_count,
                        'limit': count,
                        'period': period_seconds,
                    }
                )
                return Response(
                    {
                        'error': 'Rate limit exceeded',
                        'detail': f'Maximum {count} requests per {period_seconds} seconds',
                        'retry_after': period_seconds,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            
            # Increment counter
            try:
                if current_count == 0:
                    # First request, set with expiry
                    cache.set(cache_key, 1, period_seconds)
                else:
                    # Increment existing counter
                    cache.incr(cache_key)
            except Exception as e:
                logger.error(f"Rate limit: Error updating cache: {e}")
                # Em caso de erro de cache, permitir acesso
                return view_func(request, *args, **kwargs)
            
            # Execute view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def get_client_ip(request):
    """Extrai o IP real do cliente, considerando proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_key(request):
    """Extrai identificador do usuário autenticado."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return f"user:{request.user.id}"
    return get_client_ip(request)


def get_tenant_key(request):
    """Extrai identificador do tenant."""
    if hasattr(request, 'user') and request.user.is_authenticated and request.user.tenant:
        return f"tenant:{request.user.tenant.id}"
    return get_user_key(request)


# Decorators pré-configurados para casos comuns
def rate_limit_by_ip(rate='10/m', method='ALL'):
    """Rate limit por IP."""
    return rate_limit(key_func=get_client_ip, rate=rate, method=method)


def rate_limit_by_user(rate='100/h', method='ALL'):
    """Rate limit por usuário autenticado."""
    return rate_limit(key_func=get_user_key, rate=rate, method=method)


def rate_limit_by_tenant(rate='1000/h', method='ALL'):
    """Rate limit por tenant."""
    return rate_limit(key_func=get_tenant_key, rate=rate, method=method)

