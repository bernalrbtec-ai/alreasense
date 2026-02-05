import logging
import threading
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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


def _resolve_n8n_audio_url(tenant=None) -> str:
    if tenant:
        try:
            settings_obj = _get_tenant_ai_settings(tenant)
            if settings_obj.n8n_audio_webhook_url:
                return settings_obj.n8n_audio_webhook_url
        except Exception:
            logger.warning("Failed to resolve tenant N8N audio webhook override", exc_info=True)
    return getattr(settings, 'N8N_AUDIO_WEBHOOK', '')


def _resolve_n8n_triage_url(tenant=None) -> str:
    if tenant:
        try:
            settings_obj = _get_tenant_ai_settings(tenant)
            if settings_obj.n8n_triage_webhook_url:
                return settings_obj.n8n_triage_webhook_url
        except Exception:
            logger.warning("Failed to resolve tenant N8N triage webhook override", exc_info=True)
    return getattr(settings, 'N8N_TRIAGE_WEBHOOK', '')


def _post_to_n8n(
    action: str,
    payload: Dict[str, Any],
    timeout: float = 10.0,
    tenant=None,
    url: Optional[str] = None,
    error_message: str = "N8N webhook not configured"
) -> Dict[str, Any]:
    resolved_url = url or ""
    if not resolved_url:
        raise ValueError(error_message)

    body = {
        "action": action,
        **payload,
    }
    response = requests.post(resolved_url, json=body, timeout=timeout)
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

        response_data = _post_to_n8n(
            "triage",
            context,
            tenant=tenant,
            url=_resolve_n8n_triage_url(tenant),
            error_message="N8N triage webhook not configured",
        )
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
    settings_obj = _get_tenant_ai_settings(conversation.tenant)
    if not settings_obj.triage_enabled:
        logger.info("Triage disabled for tenant; triage skipped.")
        return
    if not _resolve_n8n_triage_url(conversation.tenant):
        logger.info("N8N triage webhook not configured; triage skipped.")
        return

    thread = threading.Thread(
        target=_triage_worker,
        args=(conversation.tenant, conversation, message, extra_context),
        daemon=True,
    )
    thread.start()


def run_test_prompt(tenant, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _resolve_n8n_triage_url(tenant):
        raise ValueError("N8N triage webhook not configured")

    context = {
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
        },
        **payload,
    }
    return _post_to_n8n(
        "test_prompt",
        context,
        tenant=tenant,
        url=_resolve_n8n_triage_url(tenant),
        error_message="N8N triage webhook not configured",
    )


def _extract_duration_ms(metadata: Optional[Dict[str, Any]]) -> Optional[int]:
    if not metadata:
        return None
    duration_ms = metadata.get('duration_ms')
    if duration_ms is None and metadata.get('duration'):
        duration_ms = int(float(metadata.get('duration')) * 1000)
    return duration_ms


def _broadcast_attachment_update(attachment, message, tenant_id: str) -> None:
    """Send attachment update to tenant websocket."""
    try:
        from apps.chat.utils.serialization import normalize_metadata

        channel_layer = get_channel_layer()
        metadata = normalize_metadata(attachment.metadata)
        metadata.pop('processing', None)

        payload = {
            'type': 'attachment_updated',
            'data': {
                'message_id': str(message.id) if message else None,
                'attachment_id': str(attachment.id),
                'file_url': attachment.file_url,
                'thumbnail_url': None,
                'mime_type': attachment.mime_type,
                'file_type': 'audio' if attachment.mime_type and attachment.mime_type.startswith('audio/') else None,
                'size_bytes': attachment.size_bytes,
                'original_filename': attachment.original_filename,
                'metadata': metadata,
                'transcription': attachment.transcription,
                'transcription_language': attachment.transcription_language,
                'ai_metadata': attachment.ai_metadata,
            }
        }
        tenant_group = f'chat_tenant_{tenant_id}'
        async_to_sync(channel_layer.group_send)(tenant_group, payload)
    except Exception:
        logger.warning("Failed to broadcast attachment update", exc_info=True)


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
    source: Optional[str] = None,
    force: bool = False,
    reset_attempts: bool = False,
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

        if not settings_obj.audio_transcription_enabled:
            logger.info("Audio transcription disabled for tenant; skipping attachment %s", attachment_id)
            return

        if not _can_auto_transcribe(settings_obj, attachment, duration_ms) and not force:
            logger.info("Audio transcription skipped for attachment %s", attachment_id)
            return

        message = None
        if message_id:
            message = Message.objects.filter(id=message_id).first()
        if not message:
            message = attachment.message

        conversation = message.conversation if message else None

        ai_metadata = attachment.ai_metadata or {}
        transcription_meta = ai_metadata.get("transcription") or {}
        attempts = int(transcription_meta.get("attempts") or 0)
        if reset_attempts:
            attempts = 0

        max_attempts = int(getattr(settings, "AI_TRANSCRIPTION_MAX_RETRIES", 3))
        retry_delay = int(getattr(settings, "AI_TRANSCRIPTION_RETRY_DELAY", 3))

        for attempt_index in range(attempts, max_attempts):
            current_attempt = attempt_index + 1
            ai_metadata = attachment.ai_metadata or {}
            ai_metadata["transcription"] = {
                "status": "processing",
                "attempts": current_attempt,
                "max_attempts": max_attempts,
            }
            attachment.ai_metadata = ai_metadata
            attachment.save(update_fields=["ai_metadata"])
            _broadcast_attachment_update(attachment, message, str(tenant_id))

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

            try:
                response_data = _post_to_n8n(
                    "transcribe",
                    payload,
                    timeout=30.0,
                    tenant=tenant,
                    url=_resolve_n8n_audio_url(tenant),
                    error_message="N8N audio webhook not configured",
                )

                transcript_text = response_data.get("transcript_text") or response_data.get("text") or ""
                language = response_data.get("language_detected") or response_data.get("language") or ""

                ai_metadata = attachment.ai_metadata or {}
                ai_metadata["transcription"] = {
                    "status": response_data.get("status", "done"),
                    "model_name": response_data.get("model_name") or response_data.get("model"),
                    "processing_time_ms": response_data.get("processing_time_ms"),
                    "attempts": current_attempt,
                    "max_attempts": max_attempts,
                }
                
                # ✅ Salvar duration_ms no ai_metadata para uso em métricas
                # Usar duration_ms extraído ou o que veio na resposta do N8N
                saved_duration_ms = response_data.get("duration_ms") or duration_ms
                if saved_duration_ms:
                    ai_metadata["duration_ms"] = int(saved_duration_ms)
                    # Também salvar em metadata para compatibilidade
                    metadata = attachment.metadata or {}
                    if "duration_ms" not in metadata:
                        metadata["duration_ms"] = int(saved_duration_ms)
                        attachment.metadata = metadata

                if transcript_text:
                    attachment.transcription = transcript_text
                if language:
                    attachment.transcription_language = language
                attachment.ai_metadata = ai_metadata
                attachment.save(update_fields=[
                    "transcription",
                    "transcription_language",
                    "ai_metadata",
                    "metadata",
                ])
                _broadcast_attachment_update(attachment, message, str(tenant_id))
                logger.info("Audio transcription stored for attachment %s", attachment_id)
                return
            except Exception as exc:
                logger.error("Failed to run audio transcription attempt %s: %s", current_attempt, exc, exc_info=True)
                ai_metadata = attachment.ai_metadata or {}
                ai_metadata["transcription"] = {
                    "status": "retrying" if current_attempt < max_attempts else "failed",
                    "error": str(exc),
                    "attempts": current_attempt,
                    "max_attempts": max_attempts,
                }
                attachment.ai_metadata = ai_metadata
                attachment.save(update_fields=["ai_metadata"])
                _broadcast_attachment_update(attachment, message, str(tenant_id))

                if current_attempt < max_attempts:
                    time.sleep(retry_delay)
                    continue
                return

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
    source: Optional[str] = None,
    force: bool = False,
    reset_attempts: bool = False,
) -> None:
    thread = threading.Thread(
        target=_transcription_worker,
        args=(tenant_id, attachment_id, message_id, conversation_id, direction, source, force, reset_attempts),
        daemon=True,
    )
    thread.start()


def run_transcription_test(tenant, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _resolve_n8n_audio_url(tenant):
        raise ValueError("N8N audio webhook not configured")

    context = {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        **payload,
    }
    return _post_to_n8n(
        "transcribe",
        context,
        timeout=30.0,
        tenant=tenant,
        url=_resolve_n8n_audio_url(tenant),
        error_message="N8N audio webhook not configured",
    )
