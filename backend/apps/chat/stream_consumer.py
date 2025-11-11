import asyncio
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from redis.exceptions import ResponseError

from apps.chat.redis_streams import (
    decode_entry,
    enqueue_mark_as_read_async,
    enqueue_send_message_async,
    ensure_stream_setup_async,
    get_stream_async_client,
    push_to_dead_letter,
)
from apps.chat.tasks import (
    InstanceTemporarilyUnavailable,
    handle_mark_message_as_read,
    handle_send_message,
)
from apps.chat.utils.instance_state import compute_backoff
from apps.chat.utils.metrics import update_worker_heartbeat, record_latency

logger = logging.getLogger(__name__)

SEND_QUEUE_KEY = 'send_message_stream'
MARK_QUEUE_KEY = 'mark_as_read_stream'


async def _xreadgroup_safe(
    stream: str,
    group: str,
    consumer: str,
    count: int,
    block_ms: int,
):
    client = await get_stream_async_client()
    try:
        return await client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: '>'},
            count=count,
            block=block_ms,
        )
    except ResponseError as exc:
        message = str(exc)
        if 'NOGROUP' in message or 'no such key' in message.lower():
            logger.warning("⚠️ [CHAT STREAM] Grupo inexistente (%s). Recriando...", stream)
            await ensure_stream_setup_async()
            return []
        raise


async def _xautoclaim_idle(
    stream: str,
    group: str,
    consumer: str,
    min_idle_ms: int,
    count: int = 10,
) -> List[Tuple[str, Dict[str, str]]]:
    """Reclama mensagens pendentes que ficaram presas em outro consumidor."""
    client = await get_stream_async_client()
    start_id = '0-0'
    reclaimed: List[Tuple[str, Dict[str, str]]] = []

    try:
        while True:
            # ✅ CORREÇÃO: redis-py async usa parâmetros posicionais, não keyword 'start'
            # Assinatura: xautoclaim(name, groupname, consumername, min_idle_time, start='0-0', count=None)
            result = await client.xautoclaim(
                stream,
                group,
                consumer,
                min_idle_ms,  # min_idle_time (posicional)
                start_id,     # start (posicional, não keyword)
                count,        # count (posicional)
            )
            # Resultado: (start_id, messages) onde messages é lista de (message_id, {field: value})
            start_id, messages = result
            if not messages:
                break
            reclaimed.extend(messages)
            if len(messages) < count:
                break
    except ResponseError as exc:
        message = str(exc)
        if 'NOGROUP' in message:
            await ensure_stream_setup_async()
            return []
        raise

    if reclaimed:
        logger.warning(
            "⚠️ [CHAT STREAM] %s mensagens recuperadas de processamento ocioso em %s",
            len(reclaimed),
            stream,
        )
    return reclaimed


def _queue_wait_seconds(enqueued_at: Optional[str]) -> Optional[float]:
    if not enqueued_at:
        return None
    enqueued_dt = parse_datetime(enqueued_at)
    if not enqueued_dt:
        return None
    if timezone.is_naive(enqueued_dt):
        enqueued_dt = timezone.make_aware(enqueued_dt, timezone.get_current_timezone())
    delta = timezone.now() - enqueued_dt
    queue_wait = delta.total_seconds()
    return queue_wait if queue_wait >= 0 else None


async def _ack(client, stream: str, group: str, entry_id: str) -> None:
    await client.xack(stream, group, entry_id)


async def _process_send_entry(
    client,
    entry_id: str,
    payload: Dict[str, Any],
    retry: int,
    worker_id: int,
) -> None:
    message_id = payload.get('message_id')
    if not message_id:
        logger.error("❌ [CHAT STREAM] Payload inválido (send): %s", payload)
        await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
        return

    queue_wait = _queue_wait_seconds(payload.get('enqueued_at'))
    if queue_wait is not None:
        record_latency(
            'send_message_stream_queue_wait',
            queue_wait,
            {
                'message_id': message_id,
                'retry': retry,
                'worker_id': worker_id,
            },
        )

    try:
        await handle_send_message(message_id, retry_count=retry)
        await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
        update_worker_heartbeat(SEND_QUEUE_KEY, worker_id)
        logger.info("✅ [CHAT STREAM] Envio concluído | message_id=%s (worker=%s)", message_id, worker_id)
    except InstanceTemporarilyUnavailable as exc:
        next_retry = retry + 1
        wait_seconds = exc.wait_seconds or compute_backoff(retry)
        state_payload = getattr(exc, 'state_payload', {}) or {}

        if next_retry > settings.CHAT_STREAM_MAX_RETRIES:
            await push_to_dead_letter(
                settings.CHAT_STREAM_SEND_NAME,
                entry_id,
                payload,
                f"Instance temporarily unavailable after retries: {state_payload}",
                next_retry,
            )
            await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
            logger.error(
                "❌ [CHAT STREAM] Instância indisponível permanentemente | message_id=%s retries=%s",
                message_id,
                next_retry,
            )
            return

        logger.warning(
            "⏳ [CHAT STREAM] Instância indisponível (%s). Retry=%s em %ss (worker=%s)",
            state_payload,
            next_retry,
            wait_seconds,
            worker_id,
        )
        await asyncio.sleep(wait_seconds)
        try:
            await enqueue_send_message_async(
                message_id,
                retry=next_retry,
                extra={'state': state_payload, 'source_entry': entry_id},
            )
        except Exception:
            logger.exception(
                "❌ [CHAT STREAM] Falha ao reenfileirar mensagem após InstanceTemporarilyUnavailable | id=%s",
                message_id,
            )
            raise
        await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
    except Exception as exc:
        next_retry = retry + 1
        error_text = str(exc)
        if next_retry > settings.CHAT_STREAM_MAX_RETRIES:
            await push_to_dead_letter(
                settings.CHAT_STREAM_SEND_NAME,
                entry_id,
                payload,
                error_text,
                next_retry,
            )
            await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
            logger.exception(
                "❌ [CHAT STREAM] Erro definitivo ao enviar mensagem | id=%s retries=%s",
                message_id,
                next_retry,
            )
            return

        logger.warning(
            "⚠️ [CHAT STREAM] Erro ao enviar mensagem (retry=%s/%s) id=%s: %s",
            next_retry,
            settings.CHAT_STREAM_MAX_RETRIES,
            message_id,
            error_text,
        )
        try:
            await enqueue_send_message_async(
                message_id,
                retry=next_retry,
                extra={'last_error': error_text, 'source_entry': entry_id},
            )
        except Exception:
            logger.exception(
                "❌ [CHAT STREAM] Falha ao reenfileirar mensagem após erro genérico | id=%s",
                message_id,
            )
            raise
        await _ack(client, settings.CHAT_STREAM_SEND_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)


async def _process_mark_entry(
    client,
    entry_id: str,
    payload: Dict[str, Any],
    retry: int,
    worker_id: int,
) -> None:
    conversation_id = payload.get('conversation_id')
    message_id = payload.get('message_id')
    if not conversation_id or not message_id:
        logger.error("❌ [CHAT STREAM] Payload inválido (mark_as_read): %s", payload)
        await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
        return

    queue_wait = _queue_wait_seconds(payload.get('enqueued_at'))
    if queue_wait is not None:
        record_latency(
            'mark_as_read_stream_queue_wait',
            queue_wait,
            {
                'message_id': message_id,
                'conversation_id': conversation_id,
                'retry': retry,
                'worker_id': worker_id,
            },
        )

    try:
        await handle_mark_message_as_read(conversation_id, message_id, retry_count=retry)
        await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
        update_worker_heartbeat(MARK_QUEUE_KEY, worker_id)
        logger.info(
            "✅ [CHAT STREAM] Read receipt enviado | conversation=%s message=%s worker=%s",
            conversation_id,
            message_id,
            worker_id,
        )
    except InstanceTemporarilyUnavailable as exc:
        next_retry = retry + 1
        wait_seconds = exc.wait_seconds or compute_backoff(retry)
        state_payload = getattr(exc, 'state_payload', {}) or {}

        if next_retry > settings.CHAT_STREAM_MAX_RETRIES:
            await push_to_dead_letter(
                settings.CHAT_STREAM_MARK_READ_NAME,
                entry_id,
                payload,
                f"Instance temporarily unavailable after retries: {state_payload}",
                next_retry,
            )
            await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
            logger.error(
                "❌ [CHAT STREAM] Read receipt falhou definitivamente (instância indisponível) conv=%s msg=%s",
                conversation_id,
                message_id,
            )
            return

        logger.warning(
            "⏳ [CHAT STREAM] Instância indisponível para mark_as_read (conv=%s msg=%s) retry=%s em %ss",
            conversation_id,
            message_id,
            next_retry,
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)
        try:
            await enqueue_mark_as_read_async(conversation_id, message_id, retry=next_retry)
        except Exception:
            logger.exception(
                "❌ [CHAT STREAM] Falha ao reenfileirar mark_as_read após instância indisponível conv=%s msg=%s",
                conversation_id,
                message_id,
            )
            raise
        await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
    except Exception as exc:
        next_retry = retry + 1
        error_text = str(exc)

        if next_retry > settings.CHAT_STREAM_MAX_RETRIES:
            await push_to_dead_letter(
                settings.CHAT_STREAM_MARK_READ_NAME,
                entry_id,
                payload,
                error_text,
                next_retry,
            )
            await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)
            logger.exception(
                "❌ [CHAT STREAM] Read receipt falhou permanentemente conv=%s msg=%s",
                conversation_id,
                message_id,
            )
            return

        logger.warning(
            "⚠️ [CHAT STREAM] Erro ao enviar read receipt (conv=%s msg=%s) retry=%s/%s: %s",
            conversation_id,
            message_id,
            next_retry,
            settings.CHAT_STREAM_MAX_RETRIES,
            error_text,
        )
        try:
            await enqueue_mark_as_read_async(conversation_id, message_id, retry=next_retry)
        except Exception:
            logger.exception(
                "❌ [CHAT STREAM] Falha ao reenfileirar mark_as_read após erro conv=%s msg=%s",
                conversation_id,
                message_id,
            )
            raise
        await _ack(client, settings.CHAT_STREAM_MARK_READ_NAME, settings.CHAT_STREAM_CONSUMER_GROUP, entry_id)


def _iter_entries(entries: Iterable[Tuple[str, List[Tuple[str, Dict[str, str]]]]]):
    for _, stream_entries in entries or []:
        for entry_id, raw_fields in stream_entries:
            yield entry_id, decode_entry(raw_fields)


async def _process_loop(
    worker_id: int,
    stream_name: str,
    processor,
    heartbeat_key: str,
    consumer_name: str,
) -> None:
    await ensure_stream_setup_async()
    client = await get_stream_async_client()
    group = settings.CHAT_STREAM_CONSUMER_GROUP
    block_ms = settings.CHAT_STREAM_BLOCK_TIMEOUT_MS
    min_idle = settings.CHAT_STREAM_RECLAIM_IDLE_MS

    update_worker_heartbeat(heartbeat_key, worker_id)
    last_heartbeat = time.monotonic()

    while True:
        try:
            entries = await _xreadgroup_safe(stream_name, group, consumer_name, count=1, block_ms=block_ms)
            handled_any = False
            for entry_id, payload in _iter_entries(entries):
                handled_any = True
                retry = payload.get('retry', 0)
                await processor(client, entry_id, payload, retry, worker_id)

            if not handled_any:
                reclaimed = await _xautoclaim_idle(stream_name, group, consumer_name, min_idle)
                for entry_id, raw_fields in reclaimed:
                    payload = decode_entry(raw_fields)
                    retry = payload.get('retry', 0)
                    await processor(client, entry_id, payload, retry, worker_id)

                await asyncio.sleep(0.1)

            now = time.monotonic()
            if now - last_heartbeat >= 5.0:
                update_worker_heartbeat(heartbeat_key, worker_id)
                last_heartbeat = now

        except asyncio.CancelledError:
            logger.info("⚠️ [CHAT STREAM] Worker cancelado (%s)", heartbeat_key)
            raise
        except Exception as exc:
            logger.exception("❌ [CHAT STREAM] Erro no worker %s: %s", heartbeat_key, exc)
            await asyncio.sleep(1)


async def start_stream_workers(
    send_workers: int = 3,
    mark_workers: int = 2,
    consumer_prefix: Optional[str] = None,
    queue_filters: Optional[Iterable[str]] = None,
) -> None:
    """
    Inicia workers para processar streams de envio/mark_as_read.
    queue_filters pode conter {"send", "mark"} para limitar.
    """
    filters = {q.strip().lower() for q in queue_filters} if queue_filters else set()
    include_send = not filters or 'send' in filters
    include_mark = not filters or 'mark' in filters

    if send_workers <= 0:
        include_send = False
    if mark_workers <= 0:
        include_mark = False

    if not include_send and not include_mark:
        logger.warning("⚠️ [CHAT STREAM] Nenhum worker configurado. Encerrando.")
        return

    await ensure_stream_setup_async()

    consumer_base = consumer_prefix or settings.CHAT_STREAM_CONSUMER_NAME or 'worker'
    tasks: List[asyncio.Task] = []

    if include_send:
        for worker_id in range(1, send_workers + 1):
            consumer_name = f"{consumer_base}-send-{worker_id}"
            tasks.append(
                asyncio.create_task(
                    _process_loop(
                        worker_id,
                        settings.CHAT_STREAM_SEND_NAME,
                        _process_send_entry,
                        SEND_QUEUE_KEY,
                        consumer_name,
                    )
                )
            )
            logger.info("🚀 [CHAT STREAM] Worker de envio iniciado (%s)", consumer_name)

    if include_mark:
        for worker_id in range(1, mark_workers + 1):
            consumer_name = f"{consumer_base}-mark-{worker_id}"
            tasks.append(
                asyncio.create_task(
                    _process_loop(
                        worker_id,
                        settings.CHAT_STREAM_MARK_READ_NAME,
                        _process_mark_entry,
                        MARK_QUEUE_KEY,
                        consumer_name,
                    )
                )
            )
            logger.info("🚀 [CHAT STREAM] Worker mark_as_read iniciado (%s)", consumer_name)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("⚠️ [CHAT STREAM] Workers cancelados")
        raise
    except Exception as exc:
        logger.exception("❌ [CHAT STREAM] Erro inesperado: %s", exc)
        raise

