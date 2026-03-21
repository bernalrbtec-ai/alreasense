"""
Timeline unificada da conversa: eventos operacionais em conversation.metadata,
mesclados com mensagens na renderização (RAG, export, UI futura).

Chave: metadata["conversation_timeline_events"] — lista append-only de dicts:
  at (ISO8601), type, schema_version, data

Grupos WhatsApp (g.us): não grava eventos (alinhado à ingestão RAG).
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

METRIC_PREFIX = "[conversation_timeline]"

TIMELINE_KEY = "conversation_timeline_events"
TIMELINE_SCHEMA_VERSION = 1
MAX_TIMELINE_EVENTS = 200

# Tipos estáveis (contrato)
EV_CONVERSATION_OPENED = "conversation_opened"
EV_CONVERSATION_REOPENED = "conversation_reopened"
EV_ASSIGNMENT_CHANGED = "assignment_changed"
EV_DEPARTMENT_TRANSFER = "department_transfer"
EV_CONVERSATION_CLOSED = "conversation_closed"

_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+[a-z0-9\-\._~\+\/]+=*)"),
    re.compile(r"(?i)(api[_\- ]?key\s*[:=]\s*[a-z0-9\-\._~\+\/=]{8,})"),
    re.compile(r"(?i)(x-amz-signature=[a-z0-9]+)"),
    re.compile(r"(?i)(x-amz-credential=[^&\s]+)"),
]
_MEDIA_PLACEHOLDERS = {"[image]", "[video]", "[document]", "[audio]", "🎨 figurinha", "📍 localização"}
_TRANSFER_INTERNAL_PREFIX = "conversa transferida:"


def is_timeline_writes_enabled() -> bool:
    """Gravação de eventos em conversation.metadata (API, webhook, bot, RAG não depende disso para ler mensagens)."""
    from django.conf import settings

    return getattr(settings, "CHAT_CONVERSATION_TIMELINE_ENABLED", True)


def is_timeline_rag_render_enabled() -> bool:
    """Se False, o texto para RAG usa só mensagens (sem eventos operacionais)."""
    from django.conf import settings

    return getattr(settings, "CHAT_TIMELINE_RAG_RENDER_ENABLED", True)


def should_skip_timeline_for_conversation(conversation) -> bool:
    phone = (getattr(conversation, "contact_phone", None) or "") or ""
    return "g.us" in phone


def _sanitize_text(value: str) -> str:
    out = value or ""
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


def _user_display(user) -> str:
    if not user:
        return ""
    fn = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    if fn:
        return fn
    return (getattr(user, "email", None) or str(getattr(user, "pk", ""))).strip()


def _dept_label(conversation) -> str:
    dept = getattr(conversation, "department", None)
    if dept is None:
        return "Inbox"
    return (getattr(dept, "name", None) or "Departamento").strip() or "Inbox"


def merge_timeline_event(
    conversation,
    event_type: str,
    data: dict[str, Any],
    *,
    at=None,
    event_id: str | None = None,
) -> None:
    """Anexa um evento ao metadata da instância em memória (caller faz save)."""
    if not is_timeline_writes_enabled():
        return
    if should_skip_timeline_for_conversation(conversation):
        return
    md = dict(conversation.metadata or {})
    events: list[dict[str, Any]] = list(md.get(TIMELINE_KEY) or [])
    ts = at if at is not None else timezone.now()
    if hasattr(ts, "isoformat"):
        at_str = ts.isoformat()
    else:
        at_str = str(ts)
    evt: dict[str, Any] = {
        "at": at_str,
        "type": event_type,
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "data": dict(data or {}),
    }
    if event_id:
        evt["id"] = str(event_id)
        if any((e.get("id") == evt["id"]) for e in events):
            return
    events.append(evt)
    while len(events) > MAX_TIMELINE_EVENTS:
        events.pop(0)
        md["conversation_timeline_truncated"] = True
    md[TIMELINE_KEY] = events
    conversation.metadata = md


def append_timeline_event_db(
    conversation_id,
    event_type: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
) -> bool:
    """
    Persiste um evento com select_for_update (transação ativa recomendada).
    Retorna False se conversa não existe, grupo g.us, ou erro.
    """
    from apps.chat.models import Conversation

    if not is_timeline_writes_enabled():
        return False

    try:
        with transaction.atomic():
            conv = (
                Conversation.objects.select_for_update(of=["self"])
                .select_related("department", "assigned_to")
                .filter(id=conversation_id)
                .first()
            )
            if not conv:
                return False
            if should_skip_timeline_for_conversation(conv):
                return False
            merge_timeline_event(conv, event_type, data, event_id=event_id)
            conv.save(update_fields=["metadata", "updated_at"])
        return True
    except Exception as exc:
        logger.error(
            "%s persist_failed conversation_id=%s event_type=%s error=%s",
            METRIC_PREFIX,
            conversation_id,
            event_type,
            exc,
            exc_info=True,
        )
        return False


def record_department_transfer_event(
    conversation_id,
    *,
    from_dept_name: str,
    to_dept_name: str,
    source: str,
    actor_user=None,
) -> None:
    actor = ""
    if actor_user is not None:
        actor = _user_display(actor_user)
    elif source:
        actor = f"bot:{source}"
    data = {
        "from_dept": from_dept_name or "Inbox",
        "to_dept": to_dept_name or "Inbox",
        "source": source or "unknown",
        "actor_label": actor,
    }
    append_timeline_event_db(conversation_id, EV_DEPARTMENT_TRANSFER, data)


def record_assignment_changed_event(
    conversation_id,
    *,
    assigned_to_user,
    previous_user_id: str | None = None,
    source: str = "api",
) -> None:
    label = _user_display(assigned_to_user) if assigned_to_user else ""
    data: dict[str, Any] = {
        "assigned_to_label": label,
        "assigned_to_id": str(assigned_to_user.pk) if assigned_to_user else "",
        "previous_assigned_to_id": previous_user_id or "",
        "source": source,
    }
    append_timeline_event_db(conversation_id, EV_ASSIGNMENT_CHANGED, data)


def record_conversation_opened_event(
    conversation_id,
    *,
    channel: str = "whatsapp",
    instance_name: str = "",
) -> None:
    data = {"channel": channel, "instance_name": (instance_name or "")[:200]}
    append_timeline_event_db(conversation_id, EV_CONVERSATION_OPENED, data)


def record_conversation_reopened_event(conversation_id, *, source: str = "whatsapp") -> None:
    append_timeline_event_db(conversation_id, EV_CONVERSATION_REOPENED, {"source": source})


def merge_conversation_closed_on_instance(conversation, *, close_source: str, closed_by_user=None) -> None:
    """Usar com conversa já carregada (dept/atendente ainda preenchidos)."""
    data = {
        "department_name": _dept_label(conversation),
        "assigned_to_label": _user_display(getattr(conversation, "assigned_to", None)),
        "close_source": close_source,
        "closed_by": _user_display(closed_by_user) if closed_by_user else "",
    }
    merge_timeline_event(conversation, EV_CONVERSATION_CLOSED, data)


def _event_sort_key(evt: dict[str, Any]) -> tuple:
    at = evt.get("at") or ""
    eid = str(evt.get("id") or "")
    return (at, 0, eid)  # eventos antes de mensagens no mesmo segundo: kind 0


def _msg_sort_key(msg) -> tuple:
    created = getattr(msg, "created_at", None) or datetime.min.replace(tzinfo=dt_timezone.utc)
    if timezone.is_naive(created):
        created = timezone.make_aware(created, timezone.get_current_timezone())
    at = created.astimezone(timezone.utc).isoformat()
    return (at, 1, str(getattr(msg, "id", "")))  # 1 = mensagem depois do evento no empate


def _format_event_line(evt: dict[str, Any]) -> str:
    t = evt.get("type") or ""
    data = evt.get("data") or {}
    at = evt.get("at") or ""
    if t == EV_CONVERSATION_OPENED:
        ch = data.get("channel") or "whatsapp"
        inst = data.get("instance_name") or ""
        extra = f" ({inst})" if inst else ""
        return f"[{at}] Contato iniciou conversa ({ch}){extra}".strip()
    if t == EV_CONVERSATION_REOPENED:
        src = data.get("source") or "unknown"
        return f"[{at}] Conversa reaberta (origem: {src})"
    if t == EV_ASSIGNMENT_CHANGED:
        aid = (data.get("assigned_to_id") or "").strip()
        label = (data.get("assigned_to_label") or "").strip()
        if aid:
            return f"[{at}] Atendimento: {label or aid}"
        return f"[{at}] Atendimento: (fila — sem atendente designado)"
    if t == EV_DEPARTMENT_TRANSFER:
        return (
            f"[{at}] Transferência: {data.get('from_dept', '?')} → {data.get('to_dept', '?')} "
            f"(por {data.get('actor_label') or data.get('source', '?')})"
        )
    if t == EV_CONVERSATION_CLOSED:
        return (
            f"[{at}] Conversa fechada — dept: {data.get('department_name', '?')}, "
            f"atendente: {data.get('assigned_to_label') or '—'}, "
            f"origem: {data.get('close_source', '?')}"
            + (
                f", por: {data.get('closed_by')}"
                if (data.get("closed_by") or "").strip()
                else ""
            )
        )
    return f"[{at}] {t}: {data}"


def _is_transfer_internal_message(msg) -> bool:
    if not getattr(msg, "is_internal", False):
        return False
    raw = (getattr(msg, "content", "") or "").strip().lower()
    return raw.startswith(_TRANSFER_INTERNAL_PREFIX)


def _message_to_line(msg) -> str | None:
    if getattr(msg, "is_internal", False):
        if _is_transfer_internal_message(msg):
            return None
        return None
    raw = (getattr(msg, "content", "") or "").strip()
    if not raw:
        return None
    if raw.lower() in _MEDIA_PLACEHOLDERS:
        return None
    created_at = getattr(msg, "created_at", None)
    ts = created_at.astimezone(timezone.utc).isoformat() if created_at else ""
    direction = getattr(msg, "direction", "incoming")
    if getattr(msg, "is_deleted", False):
        return f"[{ts}] Mensagem (apagada)"
    edit_note = " [editada]" if getattr(msg, "is_edited", False) else ""
    if direction == "incoming":
        speaker = "Cliente"
        sname = (getattr(msg, "sender_name", "") or "").strip()
        if sname:
            speaker = f"Cliente ({sname})"
    else:
        sender = getattr(msg, "sender", None)
        sname = (getattr(msg, "sender_name", "") or "").strip()
        if sender:
            speaker = f"Atendimento ({_user_display(sender)})"
        elif sname:
            speaker = f"Atendimento ({sname})"
        else:
            speaker = "Atendimento (automático)"
    return f"[{ts}] {speaker}:{edit_note} {_sanitize_text(raw)}"


def _message_line_entries(conversation) -> list[tuple[tuple, str]]:
    """Linhas derivadas só de mensagens (ordenadas), com dedup por message_id+conteúdo."""
    from apps.chat.models import Message

    msgs = list(
        Message.objects.filter(conversation_id=conversation.id).only(
            "id",
            "message_id",
            "direction",
            "is_internal",
            "content",
            "created_at",
            "sender_name",
            "sender_id",
            "is_deleted",
            "is_edited",
        )
    )
    items: list[tuple[tuple, str]] = []
    seen_msg_keys: set[str] = set()
    for msg in msgs:
        raw_full = (getattr(msg, "content", "") or "").strip()
        if not raw_full or raw_full.lower() in _MEDIA_PLACEHOLDERS:
            continue
        uniq_base = (getattr(msg, "message_id", "") or "").strip() or str(getattr(msg, "id", ""))
        uniq_hash = hashlib.sha256(
            (uniq_base + "|" + raw_full).encode("utf-8", errors="ignore")
        ).hexdigest()
        if uniq_hash in seen_msg_keys:
            continue
        seen_msg_keys.add(uniq_hash)
        line = _message_to_line(msg)
        if line:
            items.append((_msg_sort_key(msg), line))
    items.sort(key=lambda x: x[0])
    return items


def _apply_max_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    return (
        f"[... conteúdo truncado ao final, limite {max_chars} caracteres ...]\n" + tail
    )


def build_merged_timeline_items(conversation) -> list[tuple[tuple, str, str]]:
    """
    Retorna lista ordenada de (sort_key, line, kind) com kind em ('event'|'message').
    """
    items: list[tuple[tuple, str, str]] = []
    md = conversation.metadata or {}
    for evt in md.get(TIMELINE_KEY) or []:
        if not isinstance(evt, dict):
            continue
        line = _format_event_line(evt)
        items.append((_event_sort_key(evt), line, "event"))

    for sk, line in _message_line_entries(conversation):
        items.append((sk, line, "message"))

    items.sort(key=lambda x: x[0])
    return items


def message_time_bounds_utc_iso(conversation) -> tuple[str | None, str | None]:
    """Primeira/última mensagem não interna com texto útil (para metadados RAG)."""
    from apps.chat.models import Message

    times: list = []
    for m in Message.objects.filter(conversation_id=conversation.id, is_internal=False).only(
        "content", "created_at"
    ):
        raw = (getattr(m, "content", None) or "").strip()
        if not raw or raw.lower() in _MEDIA_PLACEHOLDERS:
            continue
        c = getattr(m, "created_at", None)
        if c:
            times.append(c)
    if not times:
        return None, None
    first = min(times)
    last = max(times)
    if timezone.is_naive(first):
        first = timezone.make_aware(first, timezone.get_current_timezone())
    if timezone.is_naive(last):
        last = timezone.make_aware(last, timezone.get_current_timezone())
    return first.astimezone(timezone.utc).isoformat(), last.astimezone(timezone.utc).isoformat()


def render_timeline_plaintext(conversation, *, max_chars: int) -> tuple[str, int, int, int]:
    """
    Texto único para RAG.
    Retorna (texto, total_linhas, linhas_mensagem, linhas_evento).
    Truncagem: mantém o final (comportamento anterior do transcript).
    """
    if not is_timeline_rag_render_enabled():
        entries = _message_line_entries(conversation)
        lines = [x[1] for x in entries]
        if not lines:
            return "", 0, 0, 0
        text = _apply_max_chars("\n".join(lines), max_chars)
        n = len(lines)
        return text, n, n, 0

    merged = build_merged_timeline_items(conversation)
    msg_lines = sum(1 for _sk, _ln, k in merged if k == "message")
    ev_lines = sum(1 for _sk, _ln, k in merged if k == "event")
    lines = [m[1] for m in merged]
    if not lines:
        return "", 0, 0, 0
    text = _apply_max_chars("\n".join(lines), max_chars)
    return text, len(lines), msg_lines, ev_lines
