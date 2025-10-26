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
    def invalidate_pattern(cls, pattern: str) -> int:
        """
        Invalidate all keys matching pattern
        
        Args:
            pattern: Pattern to match (e.g., 'user:*')
        
        Returns:
            Number of keys deleted
        """
        # Note: This requires Redis backend
        try:
            from django.core.cache.backends.redis import RedisCache
            backend = cache._cache
            
            if isinstance(backend, RedisCache):
                keys = backend.keys(pattern)
                if keys:
                    return backend.delete_many(keys)
            
            logger.warning(f"Pattern invalidation not supported for cache backend")
            return 0
        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {e}")
            return 0
    
    @classmethod
    def get_stats(cls) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        try:
            # Redis-specific stats
            from django.core.cache.backends.redis import RedisCache
            backend = cache._cache
            
            if isinstance(backend, RedisCache):
                info = backend.client.info('stats')
                return {
                    'total_keys': backend.client.dbsize(),
                    'hits': info.get('keyspace_hits', 0),
                    'misses': info.get('keyspace_misses', 0),
                    'memory_used': backend.client.info('memory').get('used_memory_human'),
                }
            
            return {'message': 'Stats not available for this cache backend'}
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
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

