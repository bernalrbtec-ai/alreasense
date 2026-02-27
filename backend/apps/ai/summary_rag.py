"""
Lógica de RAG (upsert/remove) para resumos de conversa. Usado por views e pelo pipeline
para evitar importação circular (apps.chat -> apps.ai.views).
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

RAG_WEBHOOK_TIMEOUT = 30

# Campos de metadata que não devem ser enviados ao n8n/pgvector (uso interno Sense).
_INTERNAL_METADATA_KEYS = frozenset({
    "auto_approved",
    "auto_approve_results",
    "auto_rejected",
    "auto_rejected_reason",
    "rag_upsert_failed",
})


def _metadata_for_payload(meta):
    """Filtra metadata para o payload: exclui contact_phone/conversation_id (já no root) e campos internos."""
    if not meta:
        return {}
    return {
        k: v
        for k, v in meta.items()
        if k not in ("contact_phone", "conversation_id") and k not in _INTERNAL_METADATA_KEYS
    }


def rag_upsert_for_summary(summary):
    """Envia resumo aprovado para o pgvector via n8n (rag-upsert)."""
    url = getattr(settings, "N8N_RAG_WEBHOOK_URL", "") or ""
    if not url:
        logger.warning("[RAG] N8N_RAG_WEBHOOK_URL não configurado, skip upsert.")
        return
    meta = summary.metadata or {}
    payload = {
        "tenant_id": str(summary.tenant_id),
        "source": "conversation_summary",
        "content": summary.content,
        "metadata": {
            "contact_phone": summary.contact_phone,
            "conversation_id": str(summary.conversation_id),
            **_metadata_for_payload(meta),
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=RAG_WEBHOOK_TIMEOUT)
        resp.raise_for_status()
        logger.info("[RAG] Upsert ok para conversation_id=%s", summary.conversation_id)
    except Exception as e:
        logger.warning("[RAG] Erro ao chamar rag-upsert para conversation_id=%s: %s", summary.conversation_id, e)
        try:
            m = dict(meta)
            m["rag_upsert_failed"] = True
            summary.metadata = m
            summary.save(update_fields=["metadata"])
        except Exception:
            pass


def rag_remove_for_summary(summary):
    """Sinaliza remoção do resumo no pgvector (n8n). Requer N8N_RAG_REMOVE_WEBHOOK_URL."""
    url = getattr(settings, "N8N_RAG_REMOVE_WEBHOOK_URL", "") or ""
    if not url:
        logger.info("[RAG] N8N_RAG_REMOVE_WEBHOOK_URL não configurado, skip remove.")
        return
    payload = {
        "tenant_id": str(summary.tenant_id),
        "source": "conversation_summary",
        "conversation_id": str(summary.conversation_id),
    }
    try:
        resp = requests.post(url, json=payload, timeout=RAG_WEBHOOK_TIMEOUT)
        resp.raise_for_status()
        logger.info("[RAG] Remove ok para conversation_id=%s", summary.conversation_id)
    except Exception as e:
        logger.warning("[RAG] Erro ao chamar rag-remove para conversation_id=%s: %s", summary.conversation_id, e)
