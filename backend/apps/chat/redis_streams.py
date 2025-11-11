import asyncio
import json
import logging
from typing import Any, Dict, Optional

import redis
import redis.asyncio as aioredis
from django.conf import settings
from django.utils import timezone
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

_sync_client: Optional[redis.Redis] = None
_async_client: Optional[aioredis.Redis] = None
_async_lock = asyncio.Lock()


def _require_stream_url() -> str:
    if not settings.CHAT_STREAM_REDIS_URL:
        raise RuntimeError("CHAT_STREAM_REDIS_URL is not configured")
    return settings.CHAT_STREAM_REDIS_URL


def get_stream_sync_client() -> redis.Redis:
    """Singleton sync client for Redis Streams (producer code)."""
    global _sync_client
    if _sync_client is not None:
        try:
            _sync_client.ping()
            return _sync_client
        except redis.exceptions.ConnectionError:
            logger.warning("⚠️ [CHAT STREAM] Sync Redis connection dropped. Recreating...")
            _sync_client = None

    connection_url = _require_stream_url()
    _sync_client = redis.Redis.from_url(
        connection_url,
        decode_responses=True,
        max_connections=20,
        socket_timeout=10,
        socket_connect_timeout=5,
    )
    _sync_client.ping()
    logger.info("✅ [CHAT STREAM] Sync client connected")
    return _sync_client


async def get_stream_async_client() -> aioredis.Redis:
    """Singleton async client for Redis Streams (consumer code)."""
    global _async_client
    if _async_client is not None:
        try:
            await _async_client.ping()
            return _async_client
        except redis.exceptions.ConnectionError:
            logger.warning("⚠️ [CHAT STREAM] Async Redis connection dropped. Recreating...")
            _async_client = None

    async with _async_lock:
        if _async_client is not None:
            return _async_client

        connection_url = _require_stream_url()
        _async_client = aioredis.from_url(
            connection_url,
            decode_responses=True,
            max_connections=50,
            socket_timeout=10,
            socket_connect_timeout=5,
        )
        await _async_client.ping()
        logger.info("✅ [CHAT STREAM] Async client connected")
        return _async_client


def _ensure_group(client: redis.Redis, stream: str, group: str) -> None:
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("✅ [CHAT STREAM] Grupo criado: %s em %s", group, stream)
    except ResponseError as exc:
        message = str(exc)
        if "BUSYGROUP" in message:
            return
        if "ERR The XGROUP CREATE command requires the key to exist" in message:
            # Criar stream vazia
            entry_id = client.xadd(stream, {"__bootstrap__": "1"})
            client.xgroup_create(stream, group, id="0", mkstream=True)
            client.xdel(stream, entry_id)
            logger.info("✅ [CHAT STREAM] Grupo criado após bootstrap: %s em %s", group, stream)
            return
        raise


def ensure_stream_setup() -> None:
    """Garantir que streams/grupos existam (chamada em producers e workers)."""
    client = get_stream_sync_client()
    group = settings.CHAT_STREAM_CONSUMER_GROUP

    for stream in (
        settings.CHAT_STREAM_SEND_NAME,
        settings.CHAT_STREAM_MARK_READ_NAME,
        settings.CHAT_STREAM_DLQ_NAME,
    ):
        if not stream:
            continue
        try:
            _ensure_group(client, stream, group)
        except Exception as exc:  # pragma: no cover - apenas log
            logger.error("❌ [CHAT STREAM] Erro ao garantir grupo em %s: %s", stream, exc)
            raise


async def ensure_stream_setup_async() -> None:
    """Versão assíncrona usada pelo worker."""
    client = await get_stream_async_client()
    group = settings.CHAT_STREAM_CONSUMER_GROUP
    for stream in (
        settings.CHAT_STREAM_SEND_NAME,
        settings.CHAT_STREAM_MARK_READ_NAME,
        settings.CHAT_STREAM_DLQ_NAME,
    ):
        if not stream:
            continue
        try:
            await client.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info("✅ [CHAT STREAM] Grupo criado (async): %s em %s", group, stream)
        except ResponseError as exc:
            message = str(exc)
            if "BUSYGROUP" in message:
                continue
            if "ERR The XGROUP CREATE command requires the key to exist" in message:
                entry_id = await client.xadd(stream, {"__bootstrap__": "1"})
                await client.xgroup_create(stream, group, id="0", mkstream=True)
                await client.xdel(stream, entry_id)
                logger.info("✅ [CHAT STREAM] Grupo criado após bootstrap (async): %s em %s", group, stream)
                continue
            raise


def _build_fields(base: Dict[str, Any]) -> Dict[str, str]:
    """Converter payload para dict de strings aceito pelo Redis."""
    fields: Dict[str, str] = {}
    for key, value in base.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            fields[key] = json.dumps(value, default=str)
        else:
            fields[key] = str(value)
    return fields


def enqueue_send_message(message_id: str, retry: int = 0, extra: Optional[Dict[str, Any]] = None) -> str:
    """Enfileira envio de mensagem (uso síncrono)."""
    ensure_stream_setup()
    client = get_stream_sync_client()
    fields = _build_fields(
        {
            "message_id": message_id,
            "retry": retry,
            "enqueued_at": timezone.now().isoformat(),
            "extra": extra or {},
        }
    )
    entry_id = client.xadd(
        settings.CHAT_STREAM_SEND_NAME,
        fields,
        maxlen=settings.CHAT_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug("📥 [CHAT STREAM] Mensagem enfileirada (send): %s -> %s", message_id, entry_id)
    return entry_id


def enqueue_mark_as_read(conversation_id: str, message_id: str, retry: int = 0) -> str:
    """Enfileira envio de read receipt (uso síncrono)."""
    ensure_stream_setup()
    client = get_stream_sync_client()
    fields = _build_fields(
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "retry": retry,
            "enqueued_at": timezone.now().isoformat(),
        }
    )
    entry_id = client.xadd(
        settings.CHAT_STREAM_MARK_READ_NAME,
        fields,
        maxlen=settings.CHAT_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug(
        "📥 [CHAT STREAM] Mensagem enfileirada (mark_as_read): conv=%s msg=%s -> %s",
        conversation_id,
        message_id,
        entry_id,
    )
    return entry_id


async def enqueue_send_message_async(message_id: str, retry: int = 0, extra: Optional[Dict[str, Any]] = None) -> str:
    await ensure_stream_setup_async()
    client = await get_stream_async_client()
    fields = _build_fields(
        {
            "message_id": message_id,
            "retry": retry,
            "enqueued_at": timezone.now().isoformat(),
            "extra": extra or {},
        }
    )
    entry_id = await client.xadd(
        settings.CHAT_STREAM_SEND_NAME,
        fields,
        maxlen=settings.CHAT_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug("📥 [CHAT STREAM] Mensagem enfileirada (async send): %s -> %s", message_id, entry_id)
    return entry_id


async def enqueue_mark_as_read_async(conversation_id: str, message_id: str, retry: int = 0) -> str:
    await ensure_stream_setup_async()
    client = await get_stream_async_client()
    fields = _build_fields(
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "retry": retry,
            "enqueued_at": timezone.now().isoformat(),
        }
    )
    entry_id = await client.xadd(
        settings.CHAT_STREAM_MARK_READ_NAME,
        fields,
        maxlen=settings.CHAT_STREAM_MAXLEN,
        approximate=True,
    )
    logger.debug(
        "📥 [CHAT STREAM] Mensagem enfileirada (async mark_as_read): conv=%s msg=%s -> %s",
        conversation_id,
        message_id,
        entry_id,
    )
    return entry_id


async def push_to_dead_letter(
    stream: str,
    original_entry_id: str,
    payload: Dict[str, Any],
    error: str,
    retry: int,
) -> str:
    await ensure_stream_setup_async()
    client = await get_stream_async_client()
    dlq_payload = _build_fields(
        {
            "original_stream": stream,
            "original_entry_id": original_entry_id,
            "payload": payload,
            "error": error,
            "retry": retry,
            "failed_at": timezone.now().isoformat(),
        }
    )
    entry_id = await client.xadd(
        settings.CHAT_STREAM_DLQ_NAME,
        dlq_payload,
        maxlen=settings.CHAT_STREAM_DLQ_MAXLEN,
        approximate=True,
    )
    logger.warning(
        "⚠️ [CHAT STREAM] Payload movido para DLQ: stream=%s entry=%s dlq=%s",
        stream,
        original_entry_id,
        entry_id,
    )
    return entry_id


def decode_entry(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Transforma campos string -> tipos adequados."""
    decoded: Dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            decoded[key] = None
            continue
        if key in {"retry"}:
            try:
                decoded[key] = int(value)
            except (TypeError, ValueError):
                decoded[key] = 0
            continue
        if key in {"extra", "payload", "state", "error_payload"}:
            try:
                decoded[key] = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded[key] = value
            continue
        decoded[key] = value
    return decoded


def get_stream_metrics() -> Dict[str, Any]:
    """Retorna métricas das streams (para dashboards)."""
    if not settings.CHAT_STREAM_REDIS_URL:
        return {}

    ensure_stream_setup()
    client = get_stream_sync_client()
    metrics: Dict[str, Any] = {}
    total_length = 0

    for label, stream_name in (
        ('send_message_stream', settings.CHAT_STREAM_SEND_NAME),
        ('mark_as_read_stream', settings.CHAT_STREAM_MARK_READ_NAME),
        ('dead_letter_stream', settings.CHAT_STREAM_DLQ_NAME),
    ):
        if not stream_name:
            continue
        try:
            info = client.xinfo_stream(stream_name)
            groups = client.xinfo_groups(stream_name)
            stream_data = {
                'name': stream_name,
                'length': info.get('length', 0),
                'last_generated_id': info.get('last-generated-id'),
                'first_entry_id': info.get('first-entry', [None])[0] if info.get('first-entry') else None,
                'groups': [
                    {
                        'name': g.get('name'),
                        'consumers': g.get('consumers'),
                        'pending': g.get('pending'),
                        'last_delivered_id': g.get('last-delivered-id'),
                    }
                    for g in groups
                ] if isinstance(groups, list) else [],
            }
            metrics[label] = stream_data
            total_length += stream_data['length']
        except ResponseError as exc:
            metrics[label] = {
                'name': stream_name,
                'error': str(exc),
                'length': 0,
            }
        except Exception as exc:  # pragma: no cover
            metrics[label] = {
                'name': stream_name,
                'error': str(exc),
                'length': 0,
            }

    metrics['total_streams_length'] = total_length
    return metrics


