"""
Serviço da Secretária IA: contexto RAG (source=secretary), upsert ao ativar perfil,
construção de contexto para o gateway (RAG + memória por contato), worker assíncrono no Inbox.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai.embeddings import embed_text
from apps.ai.models import (
    AiGatewayAudit,
    AiKnowledgeDocument,
    AiMemoryItem,
    TenantAiSettings,
    TenantSecretaryProfile,
)
from apps.ai.vector_store import search_knowledge, search_memory_for_contact

logger = logging.getLogger(__name__)

SOURCE_SECRETARY = "secretary"
SECRETARY_N8N_TIMEOUT = 20
SECRETARY_N8N_RETRY_DELAY = 2


def build_secretary_context_text(form_data: Dict[str, Any]) -> str:
    """
    Monta o texto de contexto a partir do form_data do perfil (empresa).
    Usado como conteúdo do documento RAG e para embedding.
    """
    if not form_data:
        return ""
    parts = []
    for key, value in form_data.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value = " | ".join(str(x) for x in value)
        else:
            value = str(value)
        key_label = key.replace("_", " ").strip().title()
        parts.append(f"{key_label}: {value}")
    return "\n\n".join(parts)


def upsert_secretary_rag_for_tenant(tenant_id: str) -> None:
    """
    Atualiza o documento RAG da secretária para o tenant: remove documentos
    existentes com source='secretary' e cria um novo com o form_data atual.
    Embedding gerado aqui (ao salvar/ativar), não na hora da mensagem.
    """
    try:
        profile = TenantSecretaryProfile.objects.filter(tenant_id=tenant_id).first()
        if not profile or not profile.form_data:
            # Remove qualquer documento órfão
            AiKnowledgeDocument.objects.filter(tenant_id=tenant_id, source=SOURCE_SECRETARY).delete()
            return

        text = build_secretary_context_text(profile.form_data)
        if not text.strip():
            AiKnowledgeDocument.objects.filter(tenant_id=tenant_id, source=SOURCE_SECRETARY).delete()
            return

        embedding = embed_text(text)
        with transaction.atomic():
            AiKnowledgeDocument.objects.filter(
                tenant_id=tenant_id,
                source=SOURCE_SECRETARY,
            ).delete()
            AiKnowledgeDocument.objects.create(
                tenant_id=tenant_id,
                title="Secretária IA - Dados da empresa",
                content=text,
                source=SOURCE_SECRETARY,
                tags=[],
                metadata={},
                embedding=embedding or None,
            )
        logger.info("Secretary RAG upserted for tenant %s", tenant_id)
    except Exception as e:
        logger.exception("Secretary RAG upsert failed for tenant %s: %s", tenant_id, e)
        raise


def get_secretary_rag_context(
    tenant_id: str,
    query_embedding: List[float],
    limit: int = 5,
    similarity_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """Busca conhecimento apenas source=secretary para o tenant."""
    return search_knowledge(
        tenant_id=tenant_id,
        query_embedding=query_embedding,
        limit=limit,
        similarity_threshold=similarity_threshold,
        source=SOURCE_SECRETARY,
    )


def get_secretary_memory_for_contact(
    tenant_id: str,
    contact_phone: str,
    query_embedding: List[float],
    use_memory: bool = True,
    within_days: int = 365,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retorna memória do contato para a secretária (hierarquia tenant → contato → 1 ano).
    Se use_memory for False, retorna lista vazia (LGPD).
    """
    if not use_memory or not contact_phone:
        return []
    return search_memory_for_contact(
        tenant_id=tenant_id,
        contact_phone=contact_phone,
        query_embedding=query_embedding,
        within_days=within_days,
        limit=limit,
    )


def _resolve_n8n_ai_url(tenant) -> str:
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=tenant).first()
        if settings_obj and settings_obj.n8n_ai_webhook_url:
            return settings_obj.n8n_ai_webhook_url
    except Exception:
        pass
    return getattr(settings, "N8N_AI_WEBHOOK", "")


def _build_secretary_context(conversation, message, profile: TenantSecretaryProfile) -> Dict[str, Any]:
    """Monta contexto para a Secretária: mensagens recentes, RAG source=secretary, memória por contato."""
    from apps.chat.services.business_hours_service import BusinessHoursService

    message_limit = getattr(settings, "AI_CONTEXT_MESSAGE_LIMIT", 20)
    recent_messages = list(conversation.messages.order_by("-created_at")[:message_limit])
    recent_messages.reverse()
    context_messages = [
        {
            "id": str(msg.id),
            "direction": msg.direction,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "sender_name": getattr(msg, "sender_name", "") or "",
        }
        for msg in recent_messages
    ]
    is_open, next_open_time = BusinessHoursService.is_business_hours(
        conversation.tenant, conversation.department
    )
    query_text = (message.content or "").strip()
    query_embedding = embed_text(query_text) if query_text else []
    knowledge_items = get_secretary_rag_context(
        str(conversation.tenant_id),
        query_embedding,
        limit=getattr(settings, "AI_RAG_TOP_K", 5),
    )
    memory_items = get_secretary_memory_for_contact(
        str(conversation.tenant_id),
        (conversation.contact_phone or "").strip(),
        query_embedding,
        use_memory=profile.use_memory,
        within_days=365,
        limit=getattr(settings, "AI_MEMORY_TOP_K", 5),
    )
    departments = []
    try:
        from apps.authn.models import Department
        for dept in Department.objects.filter(tenant=conversation.tenant).order_by("name"):
            departments.append({
                "id": str(dept.id),
                "name": dept.name,
                "routing_keywords": getattr(dept, "routing_keywords", []) or [],
            })
    except Exception:
        pass
    settings_obj = TenantAiSettings.objects.filter(tenant=conversation.tenant).first()
    secretary_model = (
        (getattr(settings_obj, "secretary_model", None) or "").strip()
        or (getattr(settings_obj, "agent_model", None) or "llama3.2")
    )
    prompt = (getattr(profile, "prompt", None) or "").strip()

    return {
        "agent_type": "secretary",
        "tenant": {"id": str(conversation.tenant_id), "name": conversation.tenant.name},
        "business_hours": {"is_open": is_open, "next_open_time": next_open_time},
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
        "knowledge_items": knowledge_items,
        "memory_items": memory_items,
        "departments": departments,
        "model": secretary_model,
        "metadata": {"model": secretary_model},
        "prompt": prompt,
    }


def _secretary_worker(conversation, message) -> None:
    """Worker em background: chama n8n com contexto da secretária, cria mensagem de resposta, opcionalmente atribui departamento."""
    from django.db import close_old_connections
    from apps.chat.models import Message as ChatMessage
    from apps.chat.utils.serialization import serialize_message_for_ws, serialize_conversation_for_ws
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    close_old_connections()
    start_time = time.time()
    tenant = conversation.tenant
    tenant_id = str(tenant.id)
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=tenant).first()
        profile = TenantSecretaryProfile.objects.filter(tenant=tenant).first()
        if not settings_obj or not getattr(settings_obj, "secretary_enabled", False):
            return
        if not profile or not profile.is_active:
            return
        n8n_url = _resolve_n8n_ai_url(tenant)
        if not n8n_url:
            logger.info("Secretary: n8n AI webhook not configured for tenant %s", tenant_id)
            return

        context = _build_secretary_context(conversation, message, profile)
        body = {"action": "secretary", **context}
        logger.info(
            "[SECRETARY] Chamando n8n url=%s conversation_id=%s model=%s",
            n8n_url[:50] + "..." if len(n8n_url) > 50 else n8n_url,
            conversation.id,
            body.get("model"),
        )

        last_error = None
        for attempt in range(2):
            try:
                resp = requests.post(n8n_url, json=body, timeout=SECRETARY_N8N_TIMEOUT)
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    time.sleep(SECRETARY_N8N_RETRY_DELAY)
                else:
                    logger.warning("Secretary n8n call failed for tenant %s: %s", tenant_id, e, exc_info=True)
                    return
        else:
            if last_error:
                raise last_error
            return

        reply_text = (data.get("reply_text") or "").strip()
        if not reply_text:
            return

        latency_ms = int((time.time() - start_time) * 1000)
        request_id = data.get("request_id")
        trace_id = data.get("trace_id")

        message_obj = ChatMessage.objects.create(
            conversation=conversation,
            sender=None,
            sender_name="Secretária IA",
            content=reply_text,
            direction="outgoing",
            status="pending",
            is_internal=False,
        )
        room_group_name = f"chat_tenant_{tenant_id}_conversation_{conversation.id}"
        tenant_group = f"chat_tenant_{tenant_id}"
        channel_layer = get_channel_layer()
        msg_data = serialize_message_for_ws(message_obj)
        conv_data = serialize_conversation_for_ws(conversation)
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {"type": "message_received", "message": msg_data},
        )
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {"type": "message_received", "message": msg_data, "conversation": conv_data},
        )
        from apps.chat.tasks import send_message_to_evolution
        send_message_to_evolution.delay(str(message_obj.id))

        suggested_department_id = data.get("suggested_department_id")
        summary_for_department = (data.get("summary_for_department") or "").strip()
        if suggested_department_id:
            try:
                from apps.authn.models import Department
                dept = Department.objects.filter(
                    tenant=tenant,
                    id=suggested_department_id,
                ).first()
                if dept:
                    conversation.department = dept
                    conversation.status = "open"
                    update_fields = ["department", "status"]
                    if summary_for_department:
                        meta = getattr(conversation, "metadata", None) or {}
                        if not isinstance(meta, dict):
                            meta = {}
                        meta["secretary_summary"] = summary_for_department[:2000]
                        conversation.metadata = meta
                        update_fields.append("metadata")
                    conversation.save(update_fields=update_fields)
            except Exception as e:
                logger.warning("Secretary: failed to assign department %s: %s", suggested_department_id, e)

        memory_items = data.get("memory_items") or []
        if memory_items and profile.use_memory:
            from datetime import timedelta
            retention_days = getattr(settings, "AI_MEMORY_RETENTION_DAYS", 180)
            expires_at = timezone.now() + timedelta(days=retention_days)
            for item in memory_items:
                content = (item or {}).get("content")
                if not content:
                    continue
                emb = embed_text(content)
                AiMemoryItem.objects.create(
                    tenant=tenant,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    kind=(item or {}).get("kind", "fact"),
                    content=content,
                    metadata=(item or {}).get("metadata", {}),
                    embedding=emb or None,
                    expires_at=expires_at,
                )

        try:
            AiGatewayAudit.objects.create(
                tenant=tenant,
                conversation_id=conversation.id,
                message_id=message.id,
                request_id=request_id or __import__("uuid").uuid4(),
                trace_id=trace_id or __import__("uuid").uuid4(),
                status="success",
                latency_ms=latency_ms,
                handoff=bool(suggested_department_id),
                input_summary="",  # Não logar conteúdo completo (segurança)
                output_summary=reply_text[:200] if reply_text else "",
            )
        except Exception:
            pass
    except Exception as e:
        logger.exception("Secretary worker failed for conversation %s: %s", conversation.id, e)
    finally:
        close_old_connections()


def dispatch_secretary_async(conversation, message) -> None:
    """
    Dispara o worker da Secretária em thread (Inbox + secretary_enabled).
    Chamar apenas quando conversa está no Inbox (department is None) e mensagem é incoming.
    """
    logger.info(
        "[SECRETARY] Avaliando: conv=%s dept_id=%s msg=%s",
        conversation.id, conversation.department_id, message.id,
    )
    if conversation.department_id is not None:
        logger.info(
            "[SECRETARY] Skip: conversa não está no Inbox (department_id=%s)",
            conversation.department_id,
        )
        return
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=conversation.tenant).first()
        if not settings_obj:
            logger.info("[SECRETARY] Skip: tenant sem ai_settings")
            return
        if not getattr(settings_obj, "secretary_enabled", False):
            logger.info("[SECRETARY] Skip: secretary_enabled desligado para tenant %s", conversation.tenant_id)
            return
        profile = TenantSecretaryProfile.objects.filter(tenant=conversation.tenant).first()
        if not profile:
            logger.info("[SECRETARY] Skip: tenant sem secretary_profile")
            return
        if not profile.is_active:
            logger.info("[SECRETARY] Skip: perfil da secretária inativo (is_active=False) para tenant %s", conversation.tenant_id)
            return
        n8n_url = _resolve_n8n_ai_url(conversation.tenant)
        if not n8n_url:
            logger.info("[SECRETARY] Skip: webhook da IA não configurado (n8n_ai_webhook_url vazio) para tenant %s", conversation.tenant_id)
            return
    except Exception as e:
        logger.warning("[SECRETARY] Skip: exceção ao checar condições: %s", e, exc_info=True)
        return
    logger.info(
        "[SECRETARY] Disparando worker para conversation_id=%s message_id=%s tenant_id=%s",
        conversation.id,
        message.id,
        conversation.tenant_id,
    )
    thread = threading.Thread(target=_secretary_worker, args=(conversation, message), daemon=True)
    thread.start()
