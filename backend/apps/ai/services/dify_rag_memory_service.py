from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.db import connection
from django.db import transaction
from django.utils import timezone

from apps.ai.embeddings import embed_text
from apps.ai.models import AiKnowledgeDocument
from apps.chat.models import Conversation, Message
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag

logger = logging.getLogger(__name__)

SOURCE_CHAT_TEXT_TRANSCRIPT = "chat_text_transcript"
RAG_SCOPE_TENANT_CONTACT = "tenant_contact"
DEFAULT_RETENTION_DAYS = 365
DEFAULT_MAX_CHARS = 32000


@dataclass
class TranscriptBuildResult:
    content: str
    message_count: int
    first_message_at: str | None
    last_message_at: str | None
    skipped_reason: str | None = None
    timeline_event_lines: int = 0


def _build_text_transcript(conversation: Conversation, *, max_chars: int) -> TranscriptBuildResult:
    """
    Transcript unificado: eventos operacionais (timeline) + mensagens, ordem cronológica.
    """
    from apps.chat.services.conversation_timeline import (
        message_time_bounds_utc_iso,
        render_timeline_plaintext,
    )

    content, _total_lines, msg_line_count, event_line_count = render_timeline_plaintext(
        conversation, max_chars=max_chars
    )
    first_ts, last_ts = message_time_bounds_utc_iso(conversation)

    if not (content or "").strip():
        return TranscriptBuildResult(
            content="",
            message_count=0,
            first_message_at=first_ts,
            last_message_at=last_ts,
            skipped_reason="no_messages",
            timeline_event_lines=event_line_count,
        )

    return TranscriptBuildResult(
        content=content,
        message_count=msg_line_count,
        first_message_at=first_ts,
        last_message_at=last_ts,
        skipped_reason=None if (msg_line_count or event_line_count) else "empty_text_transcript",
        timeline_event_lines=event_line_count,
    )


def _retention_days() -> int:
    raw = getattr(settings, "DIFY_RAG_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return max(1, min(days, 3650))


def _max_chars() -> int:
    raw = getattr(settings, "DIFY_RAG_TRANSCRIPT_MAX_CHARS", DEFAULT_MAX_CHARS)
    try:
        chars = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_CHARS
    return max(1000, min(chars, 200000))


def _pg_advisory_xact_lock_conversation(conversation_id: str) -> None:
    """Evita ingestão duplicada concorrente (PostgreSQL). Outros backends: sem-op."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s::text))", [str(conversation_id)])


def _should_ingest_rag_for_closed_conversation(tenant, conversation) -> bool:
    """
    Só ingere se o agente Dify aplicável (assignment inbox/departamento) tiver rag_enabled no metadata.
    """
    try:
        from apps.ai.services.dify_chat_service import resolve_dify_assignment_for_conversation
        from apps.ai.models import DifyAppCatalogItem

        assignment = resolve_dify_assignment_for_conversation(
            tenant, conversation, ignore_auto_start_flag=True
        )
        if not assignment:
            return False
        catalog_id = str(assignment.get("catalog_id") or "").strip()
        if not catalog_id:
            return False
        item = (
            DifyAppCatalogItem.objects.filter(
                id=catalog_id,
                tenant_id=getattr(tenant, "id", None),
                is_active=True,
            )
            .only("metadata")
            .first()
        )
        if not item:
            return False
        md = getattr(item, "metadata", {}) or {}
        return bool(md.get("rag_enabled"))
    except Exception as exc:
        logger.warning(
            "rag_ingest_should_skip resolve_assignment_failed conversation=%s error=%s",
            getattr(conversation, "id", conversation),
            exc,
            exc_info=True,
        )
        return False


def _transcript_content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8", errors="ignore")).hexdigest()


def _finalize_ingest_under_lock(
    conversation_id: str,
    *,
    pre_content_hash: str,
    pre_embedding: list | None,
) -> None:
    """
    Dentro de uma única transação: lock advisory + select_for_update, revalida transcript,
    evita duplicata e persiste documento + metadata.
    """
    now = timezone.now()
    with transaction.atomic():
        _pg_advisory_xact_lock_conversation(conversation_id)
        conversation = (
            Conversation.objects.select_for_update(of=["self"])
            .select_related("tenant")
            .filter(id=conversation_id)
            .first()
        )
        if not conversation or conversation.status != "closed":
            return
        tenant = conversation.tenant
        if not tenant or not _should_ingest_rag_for_closed_conversation(tenant, conversation):
            return

        built = _build_text_transcript(conversation, max_chars=_max_chars())
        transcript_hash = _transcript_content_hash(built.content)
        latest_msg = conversation.messages.order_by("-created_at", "-id").only("id").first()
        latest_msg_id = str(latest_msg.id) if latest_msg else ""

        metadata = conversation.metadata or {}
        if (
            latest_msg_id
            and metadata.get("rag_last_ingested_message_id") == latest_msg_id
            and metadata.get("rag_last_ingested_hash") == transcript_hash
        ):
            return

        if not built.content:
            metadata["rag_last_ingested_message_id"] = latest_msg_id
            metadata["rag_last_ingested_hash"] = transcript_hash
            metadata["rag_last_ingest_skipped_reason"] = built.skipped_reason or "empty"
            conversation.metadata = metadata
            conversation.save(update_fields=["metadata", "updated_at"])
            return

        embedding = pre_embedding
        if pre_content_hash != transcript_hash:
            try:
                embedding = embed_text(built.content) or None
            except Exception as emb_exc:
                logger.warning(
                    "rag_transcript_embedding_failed_under_lock conversation=%s error=%s",
                    conversation_id,
                    emb_exc,
                    exc_info=True,
                )
                embedding = None

        contact_phone_norm = normalize_contact_phone_for_rag(conversation.contact_phone or "")
        expires_at = now + timedelta(days=_retention_days())
        closed_at = (conversation.updated_at or now).astimezone(timezone.utc).isoformat()
        title = f"Conversa {conversation.contact_name or contact_phone_norm or conversation.contact_phone}"

        from apps.chat.services.conversation_timeline import TIMELINE_SCHEMA_VERSION

        doc_metadata = {
            "schema_version": 1,
            "tenant_id": str(conversation.tenant_id),
            "contact_id": str(getattr(conversation, "contact_id", "") or ""),
            "contact_phone": contact_phone_norm,
            "conversation_id": str(conversation.id),
            "channel": "whatsapp",
            "closed_at": closed_at,
            "message_count": built.message_count,
            "timeline_event_lines": built.timeline_event_lines,
            "timeline_schema_version": TIMELINE_SCHEMA_VERSION,
            "first_message_at": built.first_message_at,
            "last_message_at": built.last_message_at,
            "scope": RAG_SCOPE_TENANT_CONTACT,
            "transcript_hash": transcript_hash,
        }

        AiKnowledgeDocument.objects.create(
            tenant=tenant,
            title=title[:200],
            content=built.content,
            source=SOURCE_CHAT_TEXT_TRANSCRIPT,
            tags=["chat", "dify", "tenant_contact"],
            metadata=doc_metadata,
            embedding=embedding,
            expires_at=expires_at,
        )

        metadata["rag_last_ingested_message_id"] = latest_msg_id
        metadata["rag_last_ingested_hash"] = transcript_hash
        metadata["rag_last_ingested_at"] = now.astimezone(timezone.utc).isoformat()
        metadata.pop("rag_last_ingest_skipped_reason", None)
        conversation.metadata = metadata
        conversation.save(update_fields=["metadata", "updated_at"])

        logger.info(
            "rag_transcript_ingested tenant=%s conversation=%s messages=%s chars=%s",
            str(conversation.tenant_id),
            str(conversation.id),
            built.message_count,
            len(built.content),
        )


def ingest_closed_conversation_transcript(conversation_id: str) -> None:
    try:
        conversation = (
            Conversation.objects.select_related("tenant")
            .filter(id=conversation_id)
            .first()
        )
        if not conversation or conversation.status != "closed":
            return
        tenant = conversation.tenant
        if not tenant or not _should_ingest_rag_for_closed_conversation(tenant, conversation):
            return

        metadata = conversation.metadata or {}
        latest_msg = conversation.messages.order_by("-created_at", "-id").only("id").first()
        latest_msg_id = str(latest_msg.id) if latest_msg else ""

        built = _build_text_transcript(conversation, max_chars=_max_chars())
        transcript_hash = _transcript_content_hash(built.content)
        if (
            latest_msg_id
            and metadata.get("rag_last_ingested_message_id") == latest_msg_id
            and metadata.get("rag_last_ingested_hash") == transcript_hash
        ):
            return

        if not built.content:
            _finalize_ingest_under_lock(
                conversation_id,
                pre_content_hash=transcript_hash,
                pre_embedding=None,
            )
            return

        try:
            pre_embedding = embed_text(built.content) or None
        except Exception as emb_exc:
            logger.warning(
                "rag_transcript_embedding_failed conversation=%s error=%s",
                conversation_id,
                emb_exc,
                exc_info=True,
            )
            pre_embedding = None

        _finalize_ingest_under_lock(
            conversation_id,
            pre_content_hash=transcript_hash,
            pre_embedding=pre_embedding,
        )
    except Exception as exc:
        logger.error(
            "[rag_transcript] ingest_failed conversation=%s error=%s",
            conversation_id,
            exc,
            exc_info=True,
        )


def launch_ingest_closed_conversation(conversation_id: str) -> None:
    def _worker() -> None:
        close_old_connections()
        try:
            ingest_closed_conversation_transcript(conversation_id)
        finally:
            close_old_connections()

    thread = threading.Thread(
        target=_worker,
        daemon=True,
    )
    thread.start()
