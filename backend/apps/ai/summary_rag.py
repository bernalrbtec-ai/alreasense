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


def rag_remove_for_summary(summary, raise_on_failure=False):
    """Sinaliza remoção do resumo no pgvector (n8n). Requer N8N_RAG_REMOVE_WEBHOOK_URL. Se raise_on_failure=True, levanta em caso de URL vazia ou falha na requisição."""
    url = getattr(settings, "N8N_RAG_REMOVE_WEBHOOK_URL", "") or ""
    if not url:
        if raise_on_failure:
            raise ValueError("N8N_RAG_REMOVE_WEBHOOK_URL não configurado; não é possível remover resumo do RAG.")
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
        if raise_on_failure:
            raise
        logger.warning("[RAG] Erro ao chamar rag-remove para conversation_id=%s: %s", summary.conversation_id, e)


def rag_upsert_consolidated(tenant_id, consolidated_id, contact_phone, content, metadata=None):
    """Envia documento consolidado (um RAG por contato) para o pgvector via n8n. Levanta se URL não configurada."""
    url = getattr(settings, "N8N_RAG_WEBHOOK_URL", "") or ""
    if not url:
        raise ValueError("N8N_RAG_WEBHOOK_URL não configurado; não é possível enviar consolidado ao RAG.")
    payload = {
        "tenant_id": str(tenant_id),
        "source": "consolidated_summary",
        "content": content,
        "metadata": {
            "contact_phone": contact_phone,
            "conversation_id": str(consolidated_id),
            **(_metadata_for_payload(metadata or {})),
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=RAG_WEBHOOK_TIMEOUT)
        resp.raise_for_status()
        logger.info("[RAG] Upsert consolidado ok para consolidated_id=%s contact_phone=%s", consolidated_id, contact_phone)
    except Exception as e:
        logger.warning("[RAG] Erro ao chamar rag-upsert consolidado consolidated_id=%s: %s", consolidated_id, e)
        raise


def rag_remove_consolidated(tenant_id, consolidated_id):
    """Sinaliza remoção do documento consolidado no pgvector (n8n). Levanta se URL não configurada."""
    url = getattr(settings, "N8N_RAG_REMOVE_WEBHOOK_URL", "") or ""
    if not url:
        raise ValueError("N8N_RAG_REMOVE_WEBHOOK_URL não configurado; não é possível remover consolidado do RAG.")
    payload = {
        "tenant_id": str(tenant_id),
        "source": "consolidated_summary",
        "conversation_id": str(consolidated_id),
    }
    try:
        resp = requests.post(url, json=payload, timeout=RAG_WEBHOOK_TIMEOUT)
        resp.raise_for_status()
        logger.info("[RAG] Remove consolidado ok para consolidated_id=%s", consolidated_id)
    except Exception as e:
        logger.warning("[RAG] Erro ao chamar rag-remove consolidado consolidated_id=%s: %s", consolidated_id, e)
        raise
