"""
Pipeline de resumos ao encerrar conversa (BIA): summarize → persistir ConversationSummary (pending).
Rag-upsert (n8n/pgvector) é chamado apenas ao aprovar na tela de gestão RAG.
Executa em background; não bloqueia o fechamento da conversa.
Se N8N_SUMMARIZE_WEBHOOK_URL estiver vazio, sai sem erro.
"""
import logging
import threading
import time

import requests
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag
from apps.ai.models import ConversationSummary, TenantSecretaryProfile, TenantAiSettings

logger = logging.getLogger(__name__)

SUMMARIZE_TIMEOUT = 30
RETRY_DELAY = 2
MAX_RETRIES = 1


def _run_conversation_summary_pipeline_impl(conversation_id: str) -> None:
    """Implementação do pipeline: busca mensagens, POST summarize, persiste ConversationSummary (pending), atualiza metadata da conversa."""
    close_old_connections()
    try:
        conversation = (
            Conversation.objects.filter(id=conversation_id)
            .select_related("assigned_to", "department")
            .first()
        )
        if not conversation:
            logger.warning("[CONVERSATION SUMMARY] Conversa não encontrada: %s", conversation_id)
            return
        metadata = conversation.metadata or {}
        if metadata.get("conversation_summary_at"):
            logger.info("[CONVERSATION SUMMARY] Já processada (conversation_summary_at): %s", conversation_id)
            return
        if "g.us" in (conversation.contact_phone or ""):
            logger.info("[CONVERSATION SUMMARY] Skip: conversa de grupo: %s", conversation_id)
            return

        profile = TenantSecretaryProfile.objects.filter(tenant_id=conversation.tenant_id).first()
        if not profile or not getattr(profile, "use_memory", False):
            logger.info(
                "[CONVERSATION SUMMARY] Skip: tenant sem perfil ou use_memory=False: %s",
                conversation_id,
            )
            return

        summarize_url = getattr(settings, "N8N_SUMMARIZE_WEBHOOK_URL", "") or ""
        if not summarize_url:
            logger.info("[CONVERSATION SUMMARY] N8N_SUMMARIZE_WEBHOOK_URL não configurada, skip.")
            return

        messages_qs = Message.objects.filter(
            conversation_id=conversation_id,
            is_deleted=False,
        ).order_by("created_at").values("direction", "content", "sender_name", "created_at")
        messages_list = [
            {
                "direction": m["direction"],
                "content": (m["content"] or "")[: 10000],
                "sender_name": (m["sender_name"] or "")[: 200],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in messages_qs
        ]
        if not messages_list:
            logger.info("[CONVERSATION SUMMARY] Conversa sem mensagens, skip: %s", conversation_id)
            return

        contact_phone_normalized = normalize_contact_phone_for_rag(conversation.contact_phone or "")
        closed_at = conversation.updated_at if conversation.updated_at else timezone.now()
        ai_settings = TenantAiSettings.objects.filter(tenant_id=conversation.tenant_id).first()
        default_model = (getattr(ai_settings, "agent_model", None) or "").strip() or "qwen3:14b"
        summarize_payload = {
            "tenant_id": str(conversation.tenant_id),
            "conversation_id": str(conversation.id),
            "contact_phone": contact_phone_normalized,
            "contact_name": (conversation.contact_name or "")[: 200],
            "messages": messages_list,
            "assigned_to_id": str(conversation.assigned_to_id) if conversation.assigned_to_id else None,
            "assigned_to_name": (
                (getattr(conversation.assigned_to, "get_full_name", None) and conversation.assigned_to.get_full_name())
                if conversation.assigned_to
                else None
            )
            or (getattr(conversation.assigned_to, "name", None) if conversation.assigned_to else None)
            or "",
            "department_id": str(conversation.department_id) if conversation.department_id else None,
            "department_name": (conversation.department.name if conversation.department else None) or "",
            "closed_at": closed_at.isoformat(),
            "model": default_model,
        }
        summary = None
        summarize_response_data = {}
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(summarize_url, json=summarize_payload, timeout=SUMMARIZE_TIMEOUT)
                resp.raise_for_status()
                summarize_response_data = resp.json() if resp.content else {}
                summary = (summarize_response_data.get("summary") or "").strip()
                break
            except Exception as e:
                logger.warning(
                    "[CONVERSATION SUMMARY] Erro ao chamar summarize (tentativa %s): %s",
                    attempt + 1,
                    e,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    return
        if not summary:
            logger.warning("[CONVERSATION SUMMARY] Resposta summarize sem summary: %s", conversation_id)
            return

        subject = summarize_response_data.get("subject")
        sentiment = summarize_response_data.get("sentiment")
        satisfaction = summarize_response_data.get("satisfaction")
        if subject is None:
            subject = ""
        if sentiment is None:
            sentiment = ""
        if satisfaction is None:
            satisfaction = ""

        who_attended_id = str(conversation.assigned_to_id) if conversation.assigned_to_id else None
        who_attended_name = ""
        if conversation.assigned_to:
            who_attended_name = (
                getattr(conversation.assigned_to, "get_full_name", None)
                and conversation.assigned_to.get_full_name()
            ) or getattr(conversation.assigned_to, "name", None) or ""
        department_name = (conversation.department.name if conversation.department else None) or ""

        summary_metadata = {
            "contact_phone": contact_phone_normalized,
            "conversation_id": str(conversation.id),
            "created_at": closed_at.isoformat(),
            "closed_at": closed_at.isoformat(),
            "subject": subject,
            "sentiment": sentiment,
            "satisfaction": satisfaction,
            "who_attended_id": who_attended_id,
            "who_attended_name": who_attended_name,
            "department_name": department_name,
        }

        status_to_use = ConversationSummary.STATUS_PENDING
        try:
            from apps.ai.summary_auto_approve import should_auto_reject, evaluate_criteria, evaluate_reject_criteria
            from apps.ai.summary_rag import rag_upsert_for_summary

            rejected, reject_reason = should_auto_reject(summary)
            if rejected:
                status_to_use = ConversationSummary.STATUS_REJECTED
                summary_metadata["auto_rejected"] = True
                summary_metadata["auto_rejected_reason"] = reject_reason or "resumo indica ausência de mensagens no diálogo"
            else:
                config = getattr(profile, "summary_auto_approve_config", None) or {}
                if not isinstance(config, dict):
                    config = {}
                context = {
                    "content": summary,
                    "metadata": summary_metadata,
                    "message_count": len(messages_list),
                    "confidence": summarize_response_data.get("confidence"),
                }
                if config.get("reject_enabled"):
                    reject_result = evaluate_reject_criteria(config, context)
                    if reject_result.get("rejected"):
                        status_to_use = ConversationSummary.STATUS_REJECTED
                        summary_metadata["auto_rejected"] = True
                        summary_metadata["auto_rejected_reason"] = reject_result.get("reason") or "critério de reprovação automática"
                if status_to_use == ConversationSummary.STATUS_PENDING and config.get("enabled"):
                    eval_result = evaluate_criteria(config, context)
                    if eval_result.get("approved"):
                        status_to_use = ConversationSummary.STATUS_APPROVED
                        summary_metadata["auto_approved"] = True
                        summary_metadata["auto_approve_results"] = eval_result.get("results") or {}
        except Exception as e:
            logger.warning(
                "[CONVERSATION SUMMARY] Erro na avaliação de aprovação automática, usando PENDING: %s",
                e,
                exc_info=True,
            )

        obj, _ = ConversationSummary.objects.update_or_create(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            defaults={
                "contact_phone": contact_phone_normalized,
                "contact_name": (conversation.contact_name or "")[: 255],
                "content": summary,
                "metadata": summary_metadata,
                "status": status_to_use,
            },
        )

        if status_to_use == ConversationSummary.STATUS_APPROVED:
            try:
                rag_upsert_for_summary(obj)
            except Exception as e:
                logger.warning("[CONVERSATION SUMMARY] Erro ao chamar rag_upsert após aprovação automática: %s", e)

        conversation.refresh_from_db()
        meta = conversation.metadata or {}
        meta["conversation_summary_at"] = timezone.now().isoformat()
        conversation.metadata = meta
        conversation.save(update_fields=["metadata"])
        logger.info("[CONVERSATION SUMMARY] Pipeline concluído: %s", conversation_id)
    except Exception as e:
        logger.exception("[CONVERSATION SUMMARY] Erro no pipeline para %s: %s", conversation_id, e)
    finally:
        close_old_connections()


def run_conversation_summary_pipeline(conversation_id: str) -> None:
    """
    Dispara o pipeline de resumo em background (thread).
    Chamado pelo signal quando uma conversa passa a status=closed.
    """
    thread = threading.Thread(
        target=_run_conversation_summary_pipeline_impl,
        args=(str(conversation_id),),
        daemon=True,
    )
    thread.start()
    logger.info("[CONVERSATION SUMMARY] Pipeline em background iniciado para conversa %s", conversation_id)
