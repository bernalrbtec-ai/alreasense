"""
Debounce de mensagens inbound antes do takeover Dify: coordenação via Django cache (Redis)
e agendamento durável via Celery (countdown).

Chaves em conversation.metadata: dify_last_batched_message_id (UUID str).
Catálogo: metadata['incoming_debounce_seconds'] (0–120, 0 = desligado).
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

META_LAST_BATCHED_MSG = "dify_last_batched_message_id"
MAX_BATCH_MESSAGES = 100
MAX_BATCH_CHARS = 8000
FLOOR_TTL_SECONDS = 900  # 15 min
VERSION_KEY_TTL = 86400

_PLACEHOLDER_SKIP = frozenset({"[image]", "[video]", "[document]", "[audio]"})


def cache_key_version(tenant_id: str, conversation_id: str) -> str:
    return f"dify_in_debounce_v:{tenant_id}:{conversation_id}"


def cache_key_floor(tenant_id: str, conversation_id: str) -> str:
    return f"dify_in_burst_floor:{tenant_id}:{conversation_id}"


def parse_incoming_debounce_seconds(metadata: Any) -> int:
    if not isinstance(metadata, dict):
        return 0
    raw = metadata.get("incoming_debounce_seconds")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(n, 120))


def peek_active_dify_catalog_id(conversation_id: str, tenant_id: str) -> str | None:
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT catalog_id FROM ai_dify_conversation_state
                WHERE conversation_id = %s AND tenant_id = %s AND status = 'active'
                LIMIT 1
                """,
                [str(conversation_id), str(tenant_id)],
            )
            row = cur.fetchone()
            return str(row[0]) if row else None
    except Exception as exc:
        logger.warning("dify_debounce peek_active_catalog failed: %s", exc, exc_info=True)
        return None


def get_incoming_debounce_delay_seconds(tenant, conversation) -> int:
    """
    Delay efetivo para agendar debounce (0 = usar fluxo imediato).
    """
    from apps.ai.models import DifyAppCatalogItem
    from apps.ai.services.dify_chat_service import resolve_dify_assignment_for_conversation

    tenant_id = str(getattr(tenant, "id", "") or "")
    conv_id = str(getattr(conversation, "id", "") or "")
    if not tenant_id or not conv_id:
        return 0

    catalog_id = peek_active_dify_catalog_id(conv_id, tenant_id)
    if not catalog_id:
        assignment = resolve_dify_assignment_for_conversation(tenant, conversation)
        if not assignment:
            return 0
        catalog_id = str(assignment.get("catalog_id") or "").strip()
    if not catalog_id:
        return 0

    try:
        item = DifyAppCatalogItem.objects.filter(id=catalog_id, tenant=tenant).only("metadata").first()
    except Exception:
        item = None
    if not item:
        return 0
    return parse_incoming_debounce_seconds(item.metadata)


def _bump_debounce_version(tenant_id: str, conversation_id: str) -> int:
    key = cache_key_version(tenant_id, conversation_id)
    try:
        cache.add(key, 0, timeout=VERSION_KEY_TTL)
        v = cache.incr(key)
    except Exception as exc:
        logger.warning("dify_debounce incr failed tenant=%s conv=%s: %s — fallback v=1", tenant_id, conversation_id, exc)
        return 1
    return int(v)


def _ensure_burst_floor(tenant_id: str, conversation_id: str, created_at_iso: str) -> None:
    key = cache_key_floor(tenant_id, conversation_id)
    try:
        cache.add(key, created_at_iso, timeout=FLOOR_TTL_SECONDS)
    except Exception as exc:
        logger.warning("dify_debounce floor add failed: %s", exc, exc_info=True)


def schedule_debounced_dify_inbound(
    tenant_id: str,
    conversation_id: str,
    wa_instance_id: str | None,
    delay_seconds: int,
    message_created_at_iso: str,
) -> None:
    """
    Chamado dentro de transaction.on_commit. Agenda task Celery com countdown.
    """
    from django.conf import settings

    tid, cid = str(tenant_id), str(conversation_id)
    v = _bump_debounce_version(tid, cid)
    _ensure_burst_floor(tid, cid, message_created_at_iso)

    try:
        from apps.ai.tasks import run_dify_incoming_debounce_batch

        run_dify_incoming_debounce_batch.apply_async(
            args=[tid, cid, wa_instance_id or "", v],
            countdown=max(0, int(delay_seconds)),
            queue=getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "celery"),
        )
        logger.info(
            "dify_debounce_scheduled tenant=%s conversation=%s version=%s delay=%s",
            tid,
            cid,
            v,
            delay_seconds,
        )
    except Exception as exc:
        logger.exception(
            "dify_debounce schedule failed tenant=%s conv=%s — operador deve verificar Celery/broker: %s",
            tid,
            cid,
            exc,
        )


def _current_version_int(tenant_id: str, conversation_id: str) -> int | None:
    key = cache_key_version(tenant_id, conversation_id)
    raw = cache.get(key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return None


def _normalize_line_for_batch(content: str) -> str | None:
    text = (content or "").strip()
    if not text:
        return None
    low = text.lower()
    if low in _PLACEHOLDER_SKIP:
        return None
    # colapsar newlines internos
    return " ".join(text.splitlines()).strip() or None


def _fetch_message_ids_after_anchor(conversation_id: str, anchor_msg_id: str | None, floor_iso: str | None) -> list[str]:
    msg_table = "chat_message"
    params: list[Any] = [str(conversation_id)]
    if anchor_msg_id:
        sql = f"""
            SELECT m.id::text
            FROM {msg_table} m
            WHERE m.conversation_id = %s
              AND m.direction = 'incoming'
              AND m.is_internal = false
              AND m.is_deleted = false
              AND (m.created_at, m.id) > (
                SELECT created_at, id FROM {msg_table} WHERE id = %s LIMIT 1
              )
            ORDER BY m.created_at ASC, m.id ASC
            LIMIT %s
        """
        params.append(str(anchor_msg_id))
        params.append(MAX_BATCH_MESSAGES)
    else:
        if not floor_iso:
            return []
        sql = f"""
            SELECT id::text
            FROM {msg_table}
            WHERE conversation_id = %s
              AND direction = 'incoming'
              AND is_internal = false
              AND is_deleted = false
              AND created_at >= %s::timestamptz
            ORDER BY created_at ASC, id ASC
            LIMIT %s
        """
        params.append(str(floor_iso))
        params.append(MAX_BATCH_MESSAGES)

    with connection.cursor() as cur:
        cur.execute(sql, params)
        return [str(row[0]) for row in cur.fetchall()]


def _advance_anchor_and_clear_floor(
    tenant_id: str,
    conversation_id: str,
    last_message_id: str | None,
) -> None:
    from apps.chat.models import Conversation

    floor_key = cache_key_floor(tenant_id, conversation_id)
    try:
        cache.delete(floor_key)
    except Exception:
        pass

    if not last_message_id:
        return

    with transaction.atomic():
        conv = Conversation.objects.select_for_update().filter(id=conversation_id).first()
        if not conv:
            return
        if str(conv.tenant_id) != str(tenant_id):
            logger.error("dify_debounce tenant mismatch conv=%s", conversation_id)
            return
        meta = dict(conv.metadata or {})
        meta[META_LAST_BATCHED_MSG] = str(last_message_id)
        conv.metadata = meta
        conv.save(update_fields=["metadata", "updated_at"])


def execute_debounced_batch(
    tenant_id: str,
    conversation_id: str,
    wa_instance_id: str,
    expected_version: int,
) -> None:
    """
    Executado pelo worker Celery após countdown.
    """
    from django.db import close_old_connections

    close_old_connections()

    tid, cid = str(tenant_id), str(conversation_id)
    wa_id = str(wa_instance_id).strip() or None

    cur_v = _current_version_int(tid, cid)
    if cur_v is None or int(cur_v) != int(expected_version):
        logger.info(
            "dify_debounce_superseded tenant=%s conversation=%s expected=%s current=%s",
            tid,
            cid,
            expected_version,
            cur_v,
        )
        return

    from apps.chat.models import Conversation, Message
    from apps.tenancy.models import Tenant

    tenant = Tenant.objects.filter(id=tid).first()
    conv = Conversation.objects.select_related("tenant").filter(id=cid).first()
    if not tenant or not conv or str(conv.tenant_id) != str(tenant.id):
        logger.warning("dify_debounce_skip tenant/conv missing tenant=%s conv=%s", tid, cid)
        return

    anchor_id = (conv.metadata or {}).get(META_LAST_BATCHED_MSG)
    anchor_id = str(anchor_id).strip() if anchor_id else None
    if anchor_id and not Message.objects.filter(id=anchor_id, conversation_id=cid).exists():
        logger.info("dify_debounce_orphan_anchor conv=%s anchor=%s — usando burst_floor", cid, anchor_id)
        anchor_id = None

    floor_iso = cache.get(cache_key_floor(tid, cid))
    if isinstance(floor_iso, bytes):
        floor_iso = floor_iso.decode()

    ids = _fetch_message_ids_after_anchor(cid, anchor_id, floor_iso if not anchor_id else None)
    if not ids:
        logger.info("dify_debounce_empty_query tenant=%s conv=%s", tid, cid)
        try:
            cache.delete(cache_key_floor(tid, cid))
        except Exception:
            pass
        return

    messages = list(
        Message.objects.filter(id__in=ids).order_by("created_at", "id")
    )
    by_id = {str(m.id): m for m in messages}
    ordered = [by_id[i] for i in ids if i in by_id]

    lines: list[str] = []
    last_included_id: str | None = None
    last_candidate_id: str | None = str(ordered[-1].id) if ordered else None
    for m in ordered:
        line = _normalize_line_for_batch(m.content or "")
        if line:
            lines.append(line)
            last_included_id = str(m.id)

    combined = "\n".join(lines).strip()
    if len(combined) > MAX_BATCH_CHARS:
        combined = combined[:MAX_BATCH_CHARS]
        logger.info("dify_debounce_truncated tenant=%s conv=%s", tid, cid)

    if getattr(conv, "assigned_to_id", None):
        logger.info(
            "dify_batch_skipped_assigned tenant=%s conversation=%s",
            tid,
            cid,
        )
        _advance_anchor_and_clear_floor(tid, cid, last_candidate_id)
        return

    if not combined:
        logger.info("dify_batch_skipped_empty_after_filter tenant=%s conv=%s", tid, cid)
        _advance_anchor_and_clear_floor(tid, cid, last_candidate_id)
        return

    from apps.ai.services.dify_chat_service import (
        DifyMessageStub,
        ensure_active_dify_state_for_conversation,
        maybe_handle_dify_takeover,
    )
    from apps.notifications.models import WhatsAppInstance

    ensure_active_dify_state_for_conversation(tenant=tenant, conversation=conv)

    wa_inst = WhatsAppInstance.objects.filter(id=wa_id).first() if wa_id else None

    handled = maybe_handle_dify_takeover(
        tenant=tenant,
        conversation=conv,
        message=DifyMessageStub(content=combined),
        wa_instance=wa_inst,
        inbound_messages_for_receipt=ordered,
    )

    logger.info(
        "dify_takeover_debounced_result tenant=%s conversation=%s handled=%s batch_lines=%s",
        tid,
        cid,
        bool(handled),
        len(lines),
    )

    if handled and last_included_id:
        _advance_anchor_and_clear_floor(tid, cid, last_included_id)
