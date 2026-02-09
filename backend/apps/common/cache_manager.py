"""
✅ IMPROVEMENT: Centralized cache management with best practices
"""
import logging
import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache manager with consistent TTLs and patterns
    """
    
    # ✅ IMPROVEMENT: Standard TTL values
    TTL_MINUTE = 60
    TTL_HOUR = 3600
    TTL_DAY = 86400
    TTL_WEEK = 604800
    
    # ✅ IMPROVEMENT: Cache key prefixes for organization
    PREFIX_WEBHOOK = 'webhook'
    PREFIX_USER = 'user'
    PREFIX_TENANT = 'tenant'
    PREFIX_CAMPAIGN = 'campaign'
    PREFIX_INSTANCE = 'instance'
    PREFIX_RATE_LIMIT = 'ratelimit'
    PREFIX_QUERY = 'query'
    PREFIX_PRODUCT = 'product'
    PREFIX_PLAN = 'plan'
    PREFIX_TENANT_PRODUCT = 'tenant_product'
    PREFIX_DEPARTMENT = 'department'
    
    @classmethod
    def make_key(cls, prefix: str, *args, **kwargs) -> str:
        """
        Generate consistent cache key
        
        Args:
            prefix: Key prefix
            *args: Additional key components
            **kwargs: Key-value pairs for key
        
        Returns:
            Cache key string
        
        Example:
            key = CacheManager.make_key('user', user_id, tenant_id=123)
            # Result: 'user:456:tenant:123'
        """
        parts = [prefix]
        parts.extend(str(arg) for arg in args)
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}:{v}")
        return ':'.join(parts)
    
    @classmethod
    def get_or_set(
        cls,
        key: str,
        default_func: Callable,
        ttl: int = TTL_HOUR,
        *args,
        **kwargs
    ) -> Any:
        """
        Get from cache or set using default function
        
        Args:
            key: Cache key
            default_func: Function to call if cache miss
            ttl: Time to live in seconds
            *args: Args for default_func
            **kwargs: Kwargs for default_func
        
        Returns:
            Cached or computed value
        """
        value = cache.get(key)
        if value is not None:
            logger.debug(f"✅ Cache HIT: {key}")
            return value
        
        logger.debug(f"❌ Cache MISS: {key}")
        value = default_func(*args, **kwargs)
        cache.set(key, value, ttl)
        return value
    
    @classmethod
    def invalidate_department_cache_for_tenant(cls, tenant_id) -> int:
        """
        Invalida cache de departamentos para um tenant por chave exata.
        Funciona com qualquer backend (Redis, DB, local), não só Redis.
        """
        deleted = 0
        for scope in ('tenant', 'all'):
            key = cls.make_key(cls.PREFIX_DEPARTMENT, scope, tenant_id=str(tenant_id))
            try:
                if cache.delete(key):
                    deleted += 1
                logger.debug(f"🗑️ [CACHE] Department cache invalidado: {key}")
            except Exception as e:
                logger.warning(f"⚠️ [CACHE] Erro ao remover key {key}: {e}")
        return deleted

    @classmethod
    def invalidate_pattern(cls, pattern: str) -> int:
        """
        Invalidate all keys matching pattern
        
        Args:
            pattern: Pattern to match (e.g., 'user:*')
        
        Returns:
            Number of keys deleted
        """
        # ✅ IMPROVEMENT: Suporta múltiplos backends Redis
        try:
            backend = cache._cache
            backend_type = type(backend).__name__
            backend_module = type(backend).__module__
            
            # Verificar se é backend Redis (django.core.cache.backends.redis ou django_redis)
            is_redis = (
                'redis' in backend_module.lower() or 
                'RedisCache' in backend_type or
                hasattr(backend, 'keys') and hasattr(backend, 'delete_many')
            )
            
            if is_redis:
                try:
                    # Tentar usar método keys() e delete_many() se disponível
                    if hasattr(backend, 'keys') and hasattr(backend, 'delete_many'):
                        # Adicionar KEY_PREFIX se configurado
                        from django.conf import settings
                        key_prefix = getattr(settings, 'CACHES', {}).get('default', {}).get('KEY_PREFIX', '')
                        if key_prefix:
                            pattern = f"{key_prefix}:{pattern}" if not pattern.startswith(key_prefix) else pattern
                        
                        keys = backend.keys(pattern)
                        if keys:
                            deleted = backend.delete_many(keys)
                            logger.debug(f"🗑️ [CACHE] Invalidados {deleted} keys com padrão: {pattern}")
                            return deleted
                        else:
                            logger.debug(f"ℹ️ [CACHE] Nenhuma key encontrada com padrão: {pattern}")
                            return 0
                    else:
                        # Fallback: tentar acessar cliente Redis diretamente
                        if hasattr(backend, 'client'):
                            client = backend.client
                            if hasattr(client, 'keys') and hasattr(client, 'delete'):
                                keys = client.keys(pattern)
                                if keys:
                                    deleted = client.delete(*keys)
                                    logger.debug(f"🗑️ [CACHE] Invalidados {deleted} keys via cliente Redis: {pattern}")
                                    return deleted
                except Exception as redis_error:
                    logger.warning(f"⚠️ [CACHE] Erro ao invalidar padrão Redis {pattern}: {redis_error}")
                    return 0
            
            # Backend não suporta pattern invalidation
            logger.debug(f"ℹ️ [CACHE] Pattern invalidation não suportado para backend: {backend_module}.{backend_type}")
            return 0
        except Exception as e:
            logger.error(f"❌ [CACHE] Erro ao invalidar padrão de cache {pattern}: {e}", exc_info=True)
            return 0
    
    @classmethod
    def get_stats(cls) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        try:
            backend = cache._cache
            backend_type = type(backend).__name__
            backend_module = type(backend).__module__
            
            # ✅ IMPROVEMENT: Suporta múltiplos backends Redis
            is_redis = (
                'redis' in backend_module.lower() or 
                'RedisCache' in backend_type or
                hasattr(backend, 'client')
            )
            
            if is_redis:
                try:
                    # Tentar acessar cliente Redis
                    client = None
                    if hasattr(backend, 'client'):
                        client = backend.client
                    elif hasattr(backend, '_client'):
                        client = backend._client
                    
                    if client and hasattr(client, 'info'):
                        info = client.info('stats')
                        memory_info = client.info('memory')
                        return {
                            'total_keys': client.dbsize() if hasattr(client, 'dbsize') else 0,
                            'hits': info.get('keyspace_hits', 0),
                            'misses': info.get('keyspace_misses', 0),
                            'memory_used': memory_info.get('used_memory_human', 'N/A'),
                            'backend': f"{backend_module}.{backend_type}",
                        }
                except Exception as redis_error:
                    logger.warning(f"⚠️ [CACHE] Erro ao obter estatísticas Redis: {redis_error}")
                    return {'error': str(redis_error), 'backend': f"{backend_module}.{backend_type}"}
            
            return {
                'message': 'Stats not available for this cache backend',
                'backend': f"{backend_module}.{backend_type}"
            }
        except Exception as e:
            logger.error(f"❌ [CACHE] Erro ao obter estatísticas de cache: {e}", exc_info=True)
            return {'error': str(e)}


def cached(
    ttl: int = CacheManager.TTL_HOUR,
    prefix: Optional[str] = None,
    key_func: Optional[Callable] = None
):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds
        prefix: Cache key prefix
        key_func: Function to generate cache key from args
    
    Example:
        @cached(ttl=300, prefix='user')
        def get_user_data(user_id):
            return expensive_query(user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Generate key from function name and args
                func_name = f"{func.__module__}.{func.__name__}"
                key_parts = [prefix or func_name]
                key_parts.extend(str(arg) for arg in args)
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}:{v}")
                cache_key = ':'.join(key_parts)
                
                # Hash if too long
                if len(cache_key) > 250:
                    cache_key = hashlib.md5(cache_key.encode()).hexdigest()
            
            # Try to get from cache
            return CacheManager.get_or_set(
                cache_key,
                func,
                ttl,
                *args,
                **kwargs
            )
        
        return wrapper
    return decorator


class RateLimiter:
    """
    Redis-based rate limiter
    """
    
    @staticmethod
    def is_allowed(
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, int]:
        """
        Check if action is allowed within rate limit
        
        Args:
            key: Unique identifier (e.g., 'user:123:action')
            limit: Maximum number of actions
            window: Time window in seconds
        
        Returns:
            (allowed: bool, remaining: int)
        """
        import time
        
        current = int(time.time())
        window_key = f"{CacheManager.PREFIX_RATE_LIMIT}:{key}:{current // window}"
        
        # Increment counter
        count = cache.get(window_key, 0)
        
        if count >= limit:
            return False, 0
        
        cache.set(window_key, count + 1, window)
        return True, limit - count - 1

