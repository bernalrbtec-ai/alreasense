"""
Presença / composing na **Evolution API** (`sendPresence`).

Não aplicar a instâncias **Meta Cloud** — o typing Meta está em `MetaCloudProvider.send_typing_on`.
Usado por Dify, secretária e outros fluxos; o ramo Meta/Evolution no chamador é por `integration_type`.
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
        True se HTTP 200/201, False caso contrário ou se instância for Meta / inválida para Evolution.
    """
    if not wa_instance or not conversation:
        return False

    from apps.connections.models import EvolutionConnection
    from apps.notifications.models import WhatsAppInstance

    # Mesma regra que `get_sender` / `dify_pre_send_outbound_pause`: None ou evolution → Evolution
    _it = getattr(wa_instance, "integration_type", None) or WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION
    if _it == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
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
    inst_name = ""
    try:
        inst_name = (wa_instance.evolution_api_instance_name or "").strip()
    except Exception:
        inst_name = ""
    if not inst_name:
        inst_name = (
            (getattr(wa_instance, "instance_name", None) or "")
            or (getattr(wa_instance, "evolution_instance_name", None) or "")
        ).strip()
    if not api_url or not api_key or not inst_name:
        logger.debug("[EVO_PRESENCE] api_url, api_key ou instance_name ausente")
        return False

    delay_ms = max(500, int(float(typing_seconds) * 1000))
    presence_url = f"{str(api_url).rstrip('/')}/chat/sendPresence/{inst_name}"

    raw = (contact_phone or "").strip().replace(" ", "").lstrip("+")
    if raw.endswith("@g.us"):
        jid = raw
        digits = "".join(c for c in raw.split("@", 1)[0] if c.isdigit())
    elif raw.endswith("@s.whatsapp.net"):
        jid = raw
        digits = "".join(c for c in raw.split("@", 1)[0] if c.isdigit())
    else:
        digits = "".join(c for c in raw if c.isdigit())
        if not digits:
            logger.debug("[EVO_PRESENCE] número sem dígitos: %s", (contact_phone or "")[:30])
            return False
        jid = f"{digits}@s.whatsapp.net"
    # Evolution v2: OpenAPI com `options`; muitos servidores aceitam flat com JID
    body_variants = [
        {"number": jid, "delay": delay_ms, "presence": "composing"},
        {
            "number": jid,
            "options": {
                "delay": delay_ms,
                "presence": "composing",
                "number": jid,
            },
        },
    ]
    if digits and not jid.endswith("@g.us"):
        body_variants.append({"number": digits, "delay": delay_ms, "presence": "composing"})
    headers = {"Content-Type": "application/json", "apikey": api_key}

    try:
        logger.info(
            "[EVO_PRESENCE] composing → inst=%s delay_ms=%s jid_tail=%s",
            inst_name,
            delay_ms,
            (digits[-4:] if len(digits) >= 4 else digits) or jid[-12:],
        )
        last_status = None
        last_text = ""
        for presence_data in body_variants:
            response = requests.post(
                presence_url, json=presence_data, headers=headers, timeout=10
            )
            last_status = response.status_code
            last_text = (response.text or "")[:300]
            if response.status_code in (200, 201):
                return True
        logger.warning(
            "[EVO_PRESENCE] HTTP %s após %s variantes: %s",
            last_status,
            len(body_variants),
            last_text,
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
