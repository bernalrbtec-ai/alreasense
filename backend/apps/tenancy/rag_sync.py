"""
Sincronização TenantCompanyProfile → pgvector via webhook n8n.
Ao salvar dados da empresa, monta o chunk e envia para POST /webhook/rag-upsert.
Executa em background para não travar o save.
"""

import logging
import threading
import time

import requests
from django.conf import settings
from django.db import close_old_connections

from apps.tenancy.models import TenantCompanyProfile

logger = logging.getLogger(__name__)

RAG_WEBHOOK_TIMEOUT = 30
RAG_RETRY_DELAY = 2
RAG_MAX_RETRIES = 2


def _build_company_chunk(profile: TenantCompanyProfile) -> str:
    """
    Monta o texto do chunk a partir de TenantCompanyProfile.
    Campos vazios são omitidos.
    """
    parts = []
    if profile.razao_social:
        parts.append(f"Empresa: {profile.razao_social}")
    if profile.nome_fantasia:
        parts.append(f"Nome fantasia: {profile.nome_fantasia}")
    # documento + tipo_pessoa têm prioridade; cnpj como fallback legado
    if profile.documento and profile.tipo_pessoa:
        label = "CNPJ" if profile.tipo_pessoa == "PJ" else "CPF"
        parts.append(f"{label}: {profile.documento}")
    elif profile.cnpj:
        parts.append(f"CNPJ: {profile.cnpj}")
    if profile.endereco:
        addr = f"Endereço: {profile.endereco}"
        if profile.endereco_latitude is not None and profile.endereco_longitude is not None:
            addr += f" (Lat: {profile.endereco_latitude}, Long: {profile.endereco_longitude})"
        parts.append(addr)
    if profile.telefone or profile.email_principal:
        line_parts = []
        if profile.telefone:
            line_parts.append(f"Telefone: {profile.telefone}")
        if profile.email_principal:
            line_parts.append(f"Email: {profile.email_principal}")
        parts.append(" | ".join(line_parts))
    if profile.ramo_atuacao:
        parts.append(f"Ramo: {profile.ramo_atuacao}")
    if profile.data_fundacao:
        parts.append(f"Data de fundação: {profile.data_fundacao}")
    if profile.missao:
        parts.append(f"Missão: {profile.missao}")
    if profile.sobre_empresa:
        parts.append(f"Sobre: {profile.sobre_empresa}")
    if profile.produtos_servicos:
        parts.append(f"Produtos/Serviços: {profile.produtos_servicos}")
    if profile.logo_url:
        parts.append(f"Logo: {profile.logo_url}")
    return "\n".join(parts) if parts else ""


def _sync_company_chunk_worker(tenant_id: str) -> None:
    """Worker em background: monta chunk e chama webhook RAG."""
    close_old_connections()  # evita conexão herdada do thread da request
    webhook_url = getattr(settings, "N8N_RAG_WEBHOOK_URL", "") or ""
    if not webhook_url:
        logger.info("[RAG SYNC] N8N_RAG_WEBHOOK_URL não configurado, skip.")
        return

    try:
        profile = TenantCompanyProfile.objects.get(tenant_id=tenant_id)
    except TenantCompanyProfile.DoesNotExist:
        logger.warning("[RAG SYNC] TenantCompanyProfile não encontrado para tenant %s", tenant_id)
        return

    content = _build_company_chunk(profile)
    if not content.strip():
        logger.info("[RAG SYNC] Chunk vazio para tenant %s, skip.", tenant_id)
        return

    payload = {
        "tenant_id": str(tenant_id),
        "source": "company",
        "content": content,
        "metadata": {},
    }

    for attempt in range(RAG_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=RAG_WEBHOOK_TIMEOUT,
            )
            resp.raise_for_status()
            logger.info("[RAG SYNC] Chunk enviado com sucesso para tenant %s", tenant_id)
            return
        except Exception as e:
            if attempt < RAG_MAX_RETRIES:
                time.sleep(RAG_RETRY_DELAY * (attempt + 1))
            else:
                logger.warning(
                    "[RAG SYNC] Falha após %s tentativas para tenant %s: %s",
                    RAG_MAX_RETRIES + 1,
                    tenant_id,
                    e,
                    exc_info=True,
                )


def sync_company_chunk_async(tenant_id: str) -> None:
    """
    Dispara sincronização do chunk da empresa para o pgvector (n8n) em background.
    Chamar após salvar TenantCompanyProfile.
    """
    tid = str(tenant_id)
    if not getattr(settings, "N8N_RAG_WEBHOOK_URL", ""):
        return
    thread = threading.Thread(target=_sync_company_chunk_worker, args=(tid,), daemon=True)
    thread.start()
    logger.debug("[RAG SYNC] Thread disparada para tenant %s", tid)
