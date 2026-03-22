"""
Presença / composing na Evolution API (sendPresence).
Usado por Dify, secretária e outros fluxos que precisam de indicador "digitando".
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


def send_evolution_composing_presence(
    conversation: Any,
    wa_instance: Any,
    typing_seconds: float,
) -> bool:
    """
    Envia presence=composing para o número da conversa na instância Evolution indicada.

    Returns:
        True se HTTP 200/201, False caso contrário ou se instância não for Evolution.
    """
    if not wa_instance or not conversation:
        return False

    from apps.connections.models import EvolutionConnection
    from apps.notifications.models import WhatsAppInstance

    if getattr(wa_instance, "integration_type", None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
        return False

    contact_phone = (getattr(conversation, "contact_phone", None) or "").strip()
    if not contact_phone:
        logger.debug("[EVO_PRESENCE] sem contact_phone")
        return False

    evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
    api_url = getattr(wa_instance, "api_url", None) or (
        evolution_server.base_url if evolution_server else None
    )
    api_key = getattr(wa_instance, "api_key", None) or (
        evolution_server.api_key if evolution_server else None
    )
    inst_name = (
        (getattr(wa_instance, "instance_name", None) or "")
        or (getattr(wa_instance, "evolution_instance_name", None) or "")
    ).strip()
    if not api_url or not api_key or not inst_name:
        logger.debug("[EVO_PRESENCE] api_url, api_key ou instance_name ausente")
        return False

    delay_ms = max(500, int(float(typing_seconds) * 1000))
    presence_url = f"{str(api_url).rstrip('/')}/chat/sendPresence/{inst_name}"
    presence_data = {
        "number": contact_phone,
        "delay": delay_ms,
        "presence": "composing",
    }
    headers = {"Content-Type": "application/json", "apikey": api_key}

    try:
        logger.info(
            "[EVO_PRESENCE] composing → inst=%s delay_ms=%s",
            inst_name,
            delay_ms,
        )
        response = requests.post(
            presence_url, json=presence_data, headers=headers, timeout=10
        )
        if response.status_code in (200, 201):
            return True
        logger.warning(
            "[EVO_PRESENCE] HTTP %s: %s",
            response.status_code,
            (response.text or "")[:200],
        )
        return False
    except Exception as e:
        logger.warning("[EVO_PRESENCE] erro: %s", e, exc_info=True)
        return False


def resolve_wa_instance_for_presence(conversation: Any) -> Optional[Any]:
    """
    Mesma prioridade que secretária: instância da conversa, senão primeira ativa do tenant.
    """
    from django.db.models import Q

    from apps.notifications.models import WhatsAppInstance

    instance = None
    if conversation.instance_name and str(conversation.instance_name).strip():
        instance = WhatsAppInstance.objects.filter(
            Q(instance_name=str(conversation.instance_name).strip())
            | Q(evolution_instance_name=str(conversation.instance_name).strip()),
            tenant=conversation.tenant,
            is_active=True,
            status="active",
        ).first()
    if not instance:
        instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status="active",
        ).first()
    return instance
