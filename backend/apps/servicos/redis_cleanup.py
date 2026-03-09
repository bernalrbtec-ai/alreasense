"""
Lógica de limpeza Redis (cache profile_pic, webhook).
Usa KEY_PREFIX de settings; SCAN + DEL; timeouts; não usa KEYS.
"""
import logging
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Timeout para operações de limpeza (segundos)
CLEANUP_SOCKET_TIMEOUT = 120
SCAN_COUNT = 500


def _redis_url_for_db(db: int) -> str:
    """Retorna REDIS_URL apontando para o DB indicado (ex.: redis://host:6379/2)."""
    base = (getattr(settings, "REDIS_URL", "") or "").strip()
    if not base:
        return ""
    # REDIS_URL é tipo redis://[user:pass@]host:port/0
    parts = base.rsplit("/", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0] + "/" + str(db)
    return base.rstrip("/") + "/" + str(db)


def _get_client(db: int):
    """Cliente Redis para o DB indicado. Retorna None se REDIS_URL vazia."""
    url = _redis_url_for_db(db)
    if not url:
        return None
    try:
        return redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=CLEANUP_SOCKET_TIMEOUT,
        )
    except Exception as e:
        logger.warning("Redis client for db %s: %s", db, e)
        return None


def _get_cache_key_prefix() -> str:
    """Prefix do cache Django (ex.: alrea_cache)."""
    caches = getattr(settings, "CACHES", {}) or {}
    default = caches.get("default", {}) or {}
    return (default.get("KEY_PREFIX") or "alrea_cache").strip()


def run_redis_cleanup(
    profile_pic: bool = True,
    webhook: bool = False,
) -> dict[str, Any]:
    """
    Executa limpeza de keys no Redis.
    - profile_pic: remove keys do cache de fotos de perfil (DB 2, padrão alrea_cache:profile_pic:*)
    - webhook: remove keys do cache de webhooks (DB 0, padrão webhook:*)

    Retorna: { keys_deleted_profile_pic, keys_deleted_webhook, bytes_freed_estimate }
    bytes_freed_estimate pode ser None (não calculado).
    """
    result = {
        "keys_deleted_profile_pic": 0,
        "keys_deleted_webhook": 0,
        "bytes_freed_estimate": None,
    }

    if profile_pic:
        prefix = _get_cache_key_prefix()
        pattern = f"{prefix}:profile_pic:*"
        client = _get_client(2)
        if client:
            try:
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=SCAN_COUNT)
                    if keys:
                        n = client.delete(*keys)
                        deleted += n
                    if cursor == 0:
                        break
                result["keys_deleted_profile_pic"] = deleted
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.exception("Redis cleanup profile_pic: %s", e)
                raise
            finally:
                client.close()
        else:
            raise RuntimeError("Redis não configurado ou indisponível")

    if webhook:
        pattern = "webhook:*"
        client = _get_client(0)
        if client:
            try:
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=SCAN_COUNT)
                    if keys:
                        n = client.delete(*keys)
                        deleted += n
                    if cursor == 0:
                        break
                result["keys_deleted_webhook"] = deleted
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.exception("Redis cleanup webhook: %s", e)
                raise
            finally:
                client.close()
        else:
            raise RuntimeError("Redis não configurado ou indisponível")

    return result
