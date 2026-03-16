import logging
from typing import Optional

import requests
from django.conf import settings
from django.db import transaction

from apps.tenancy.models import Tenant, TypebotWorkspace

logger = logging.getLogger(__name__)


def _get_typebot_admin_base() -> Optional[str]:
    """
    Retorna a base da API admin do Typebot a partir de TYPEBOT_API_BASE.
    Ex.: https://typebot.alrea.ai/api/v1 -> https://typebot.alrea.ai
    """
    base = (getattr(settings, "TYPEBOT_API_BASE", None) or "").strip().rstrip("/")
    if not base:
        return None
    # Remover sufixo /api/v1 se presente
    if base.endswith("/api/v1"):
        return base[: -len("/api/v1")]
    return base


def get_or_create_typebot_workspace(tenant: Tenant) -> Optional[TypebotWorkspace]:
    """
    Garante que o tenant tenha um workspace Typebot associado.
    - Se já existir, retorna.
    - Senão, cria via API admin do Typebot (POST /v1/workspaces) quando possível.
    Em qualquer erro, loga e retorna None sem quebrar o request.
    """
    if not tenant or not getattr(tenant, "id", None):
        return None
    try:
        existing = getattr(tenant, "typebot_workspace", None)
    except TypebotWorkspace.DoesNotExist:
        existing = None
    except Exception:
        existing = None
    if isinstance(existing, TypebotWorkspace):
        return existing

    admin_base = _get_typebot_admin_base()
    api_key = (getattr(settings, "TYPEBOT_ADMIN_API_KEY", None) or "").strip()
    if not admin_base or not api_key:
        logger.info(
            "[TYPEBOT][WORKSPACE] Admin base ou API key não configuradas; "
            "não será criado workspace automático para tenant=%s",
            tenant.id,
        )
        return None

    url = f"{admin_base}/v1/workspaces"
    payload = {
        "name": tenant.name[:120] if tenant.name else "Workspace Sense",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
        workspace_id = (data.get("id") or data.get("workspaceId") or "").strip()
        name = (data.get("name") or payload["name"]).strip()
        if not workspace_id:
            logger.warning(
                "[TYPEBOT][WORKSPACE] Resposta sem id ao criar workspace tenant=%s data=%s",
                tenant.id,
                list(data.keys()),
            )
            return None
    except requests.RequestException as e:
        logger.warning(
            "[TYPEBOT][WORKSPACE] Falha ao criar workspace para tenant=%s: %s",
            tenant.id,
            e,
        )
        return None
    except Exception as e:
        logger.warning(
            "[TYPEBOT][WORKSPACE] Erro inesperado ao criar workspace tenant=%s: %s",
            tenant.id,
            e,
            exc_info=True,
        )
        return None

    try:
        with transaction.atomic():
            ws, created = TypebotWorkspace.objects.select_for_update().get_or_create(
                tenant=tenant,
                defaults={
                    "workspace_id": workspace_id,
                    "name": name,
                },
            )
            if not created and ws.workspace_id != workspace_id:
                # Não sobrescrever automaticamente um workspace existente diferente;
                # apenas logar para investigação futura.
                logger.info(
                    "[TYPEBOT][WORKSPACE] Workspace existente diferente para tenant=%s "
                    "local=%s api=%s",
                    tenant.id,
                    ws.workspace_id,
                    workspace_id,
                )
            return ws
    except Exception as e:
        logger.warning(
            "[TYPEBOT][WORKSPACE] Erro ao persistir workspace tenant=%s id=%s: %s",
            tenant.id,
            workspace_id,
            e,
            exc_info=True,
        )
        return None

