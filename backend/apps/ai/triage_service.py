import logging
import threading
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.ai.embeddings import embed_text
from apps.ai.models import AiMemoryItem, AiTriageResult
from apps.ai.vector_store import search_memory, search_knowledge
from apps.chat.services.business_hours_service import BusinessHoursService

logger = logging.getLogger(__name__)


def _get_tenant_ai_settings(tenant):
    from apps.ai.models import TenantAiSettings
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


def _resolve_n8n_url(tenant=None) -> str:
    if tenant:
        try:
            settings_obj = _get_tenant_ai_settings(tenant)
            if settings_obj.n8n_webhook_url:
                return settings_obj.n8n_webhook_url
        except Exception:
            logger.warning("Failed to resolve tenant N8N webhook override", exc_info=True)
    return getattr(settings, 'N8N_AI_WEBHOOK', '')


def _n8n_url() -> str:
    return _resolve_n8n_url()


def _post_to_n8n(
    action: str,
    payload: Dict[str, Any],
    timeout: float = 10.0,
    tenant=None
) -> Dict[str, Any]:
    url = _resolve_n8n_url(tenant)
    if not url:
        raise ValueError("N8N_AI_WEBHOOK not configured")

    body = {
        "action": action,
        **payload,
    }
    response = requests.post(url, json=body, timeout=timeout)
    response.raise_for_status()
    return response.json() if response.content else {}


def _build_context(conversation, message) -> Dict[str, Any]:
    message_limit = getattr(settings, 'AI_CONTEXT_MESSAGE_LIMIT', 20)
    memory_top_k = getattr(settings, 'AI_MEMORY_TOP_K', 5)
    knowledge_top_k = getattr(settings, 'AI_RAG_TOP_K', 5)

    recent_messages = list(
        conversation.messages.order_by('-created_at')[:message_limit]
    )
    recent_messages.reverse()

    context_messages = [
        {
            "id": str(msg.id),
            "direction": msg.direction,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "sender_name": msg.sender_name,
        }
        for msg in recent_messages
    ]

    is_open, next_open_time = BusinessHoursService.is_business_hours(
        conversation.tenant, conversation.department
    )

    query_embedding = embed_text(message.content) if message.content else []
    memory_items = search_memory(
        tenant_id=str(conversation.tenant_id),
        query_embedding=query_embedding,
        limit=memory_top_k,
    )
    knowledge_items = search_knowledge(
        tenant_id=str(conversation.tenant_id),
        query_embedding=query_embedding,
        limit=knowledge_top_k,
    )

    return {
        "tenant": {
            "id": str(conversation.tenant_id),
            "name": conversation.tenant.name,
        },
        "business_hours": {
            "is_open": is_open,
            "next_open_time": next_open_time,
        },
        "conversation": {
            "id": str(conversation.id),
            "status": conversation.status,
            "contact_name": conversation.contact_name,
            "contact_phone": conversation.contact_phone,
            "department": conversation.department.name if conversation.department else None,
            "department_id": str(conversation.department_id) if conversation.department_id else None,
        },
        "message": {
            "id": str(message.id),
            "direction": message.direction,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
        "messages": context_messages,
        "memory_items": memory_items,
        "knowledge_items": knowledge_items,
    }


def _save_memory_items(tenant, conversation, message, items: List[Dict[str, Any]]) -> None:
    if not items:
        return

    retention_days = getattr(settings, 'AI_MEMORY_RETENTION_DAYS', 180)
    expires_at = timezone.now() + timedelta(days=retention_days)
    for item in items:
        content = (item or {}).get('content')
        if not content:
            continue
        embedding = embed_text(content)
        AiMemoryItem.objects.create(
            tenant=tenant,
            conversation_id=conversation.id if conversation else None,
            message_id=message.id if message else None,
            kind=(item or {}).get('kind', 'fact'),
            content=content,
            metadata=(item or {}).get('metadata', {}),
            embedding=embedding or None,
            expires_at=expires_at,
        )


def _triage_worker(tenant, conversation, message, extra_context: Optional[Dict[str, Any]] = None) -> None:
    close_old_connections()
    start_time = time.time()
    context: Dict[str, Any] = {}
    try:
        context = _build_context(conversation, message)
        if extra_context:
            context.update(extra_context)

        response_data = _post_to_n8n("triage", context, tenant=tenant)
        latency_ms = int((time.time() - start_time) * 1000)

        AiTriageResult.objects.create(
            tenant=tenant,
            conversation_id=conversation.id if conversation else None,
            message_id=message.id if message else None,
            action="triage",
            model_name=response_data.get("model", ""),
            prompt_version=response_data.get("prompt_version", ""),
            latency_ms=latency_ms,
            status="success",
            result=response_data,
            raw_request=context,
            raw_response=response_data,
        )

        memory_items = response_data.get("memory_items", [])
        _save_memory_items(tenant, conversation, message, memory_items)

    except Exception as exc:
        logger.error("Failed to run triage: %s", exc, exc_info=True)
        latency_ms = int((time.time() - start_time) * 1000)
        AiTriageResult.objects.create(
            tenant=tenant,
            conversation_id=conversation.id if conversation else None,
            message_id=message.id if message else None,
            action="triage",
            latency_ms=latency_ms,
            status="failed",
            result={"error": str(exc)},
            raw_request=context or extra_context or {},
        )
    finally:
        close_old_connections()


def dispatch_triage_async(conversation, message, extra_context: Optional[Dict[str, Any]] = None) -> None:
    if not _resolve_n8n_url(conversation.tenant):
        logger.info("N8N_AI_WEBHOOK not configured; triage skipped.")
        return

    thread = threading.Thread(
        target=_triage_worker,
        args=(conversation.tenant, conversation, message, extra_context),
        daemon=True,
    )
    thread.start()


def run_test_prompt(tenant, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _resolve_n8n_url(tenant):
        raise ValueError("N8N_AI_WEBHOOK not configured")

    context = {
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
        },
        **payload,
    }
    return _post_to_n8n("test_prompt", context, tenant=tenant)


def _extract_duration_ms(metadata: Optional[Dict[str, Any]]) -> Optional[int]:
    if not metadata:
        return None
    duration_ms = metadata.get('duration_ms')
    if duration_ms is None and metadata.get('duration'):
        duration_ms = int(float(metadata.get('duration')) * 1000)
    return duration_ms


def _can_auto_transcribe(settings_obj, attachment, duration_ms: Optional[int]) -> bool:
    if not settings_obj.ai_enabled:
        return False
    if not settings_obj.audio_transcription_enabled:
        return False
    if not settings_obj.transcription_auto:
        return False
    if not attachment or not attachment.file_url:
        return False
    if not attachment.mime_type or not attachment.mime_type.startswith('audio/'):
        return False
    if attachment.transcription:
        return False

    size_bytes = attachment.size_bytes or 0
    max_bytes = max(settings_obj.transcription_max_mb or 0, 0) * 1024 * 1024
    if max_bytes and size_bytes > max_bytes:
        return False

    min_ms = max(settings_obj.transcription_min_seconds or 0, 0) * 1000
    if duration_ms is not None and min_ms and duration_ms < min_ms:
        return False

    return True


def _transcription_worker(
    tenant_id: str,
    attachment_id: str,
    message_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    direction: Optional[str] = None,
    source: Optional[str] = None
) -> None:
    close_old_connections()
    try:
        from apps.chat.models import MessageAttachment, Message

        attachment = MessageAttachment.objects.select_related(
            'tenant',
            'message',
            'message__conversation',
        ).get(id=attachment_id)
        tenant = attachment.tenant
        settings_obj = _get_tenant_ai_settings(tenant)
        duration_ms = _extract_duration_ms(attachment.metadata or {})

        if not _can_auto_transcribe(settings_obj, attachment, duration_ms):
            logger.info("Audio transcription skipped for attachment %s", attachment_id)
            return

        message = None
        if message_id:
            message = Message.objects.filter(id=message_id).first()
        if not message:
            message = attachment.message

        conversation = message.conversation if message else None

        payload = {
            "tenant_id": str(tenant_id),
            "conversation_id": str(conversation_id or (conversation.id if conversation else "")) or None,
            "message_id": str(message_id or (message.id if message else "")) or None,
            "media_url": attachment.file_url,
            "duration_ms": duration_ms,
            "size_bytes": attachment.size_bytes,
            "direction": direction or (message.direction if message else None),
            "agent_model": settings_obj.agent_model,
            "source": source,
        }

        response_data = _post_to_n8n("transcribe", payload, timeout=30.0, tenant=tenant)

        transcript_text = response_data.get("transcript_text") or response_data.get("text") or ""
        language = response_data.get("language_detected") or response_data.get("language") or ""

        ai_metadata = attachment.ai_metadata or {}
        ai_metadata["transcription"] = {
            "status": response_data.get("status", "done"),
            "model_name": response_data.get("model_name") or response_data.get("model"),
            "processing_time_ms": response_data.get("processing_time_ms"),
        }

        if transcript_text:
            attachment.transcription = transcript_text
        if language:
            attachment.transcription_language = language
        attachment.ai_metadata = ai_metadata
        attachment.save(update_fields=[
            "transcription",
            "transcription_language",
            "ai_metadata",
        ])
        logger.info("Audio transcription stored for attachment %s", attachment_id)

    except Exception as exc:
        logger.error("Failed to run audio transcription: %s", exc, exc_info=True)
    finally:
        close_old_connections()


def dispatch_transcription_async(
    tenant_id: str,
    attachment_id: str,
    message_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    direction: Optional[str] = None,
    source: Optional[str] = None
) -> None:
    try:
        from apps.chat.models import MessageAttachment
        attachment = MessageAttachment.objects.select_related('tenant').get(id=attachment_id)
        settings_obj = _get_tenant_ai_settings(attachment.tenant)
        duration_ms = _extract_duration_ms(attachment.metadata or {})
        if not _can_auto_transcribe(settings_obj, attachment, duration_ms):
            logger.info("Audio transcription auto-disabled for attachment %s", attachment_id)
            return
        if not _resolve_n8n_url(attachment.tenant):
            logger.info("N8N_AI_WEBHOOK not configured; transcription skipped.")
            return
    except Exception as exc:
        logger.error("Unable to enqueue transcription: %s", exc, exc_info=True)
        return

    thread = threading.Thread(
        target=_transcription_worker,
        args=(tenant_id, attachment_id, message_id, conversation_id, direction, source),
        daemon=True,
    )
    thread.start()


def run_transcription_test(tenant, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _resolve_n8n_url(tenant):
        raise ValueError("N8N_AI_WEBHOOK not configured")

    context = {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        **payload,
    }
    return _post_to_n8n("transcribe", context, timeout=30.0, tenant=tenant)
