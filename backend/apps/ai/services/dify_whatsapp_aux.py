"""
Sinais auxiliares no fluxo Dify: read receipts inbound e pausa com typing antes do outbound.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterable, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def dify_mark_inbound_messages_read(
    conversation: Any,
    messages: Optional[Iterable[Any]],
    preferred_wa_instance: Any = None,
) -> None:
    """
    Marca como lidas (WhatsApp) as mensagens inbound listadas, sem abortar o takeover em erro.

    preferred_wa_instance: alinha com a instância usada para enviar a resposta do Dify (agente),
    evitando read na instância errada quando difere de conversation.instance_name.
    """
    if not getattr(settings, "DIFY_MARK_INBOUND_READ", True):
        return
    if not messages or not conversation:
        return

    from apps.chat.webhooks import send_read_receipt

    eligible = []
    for msg in messages:
        if msg is None:
            continue
        if getattr(msg, "direction", "") != "incoming":
            continue
        if getattr(msg, "is_deleted", False):
            continue
        mid = getattr(msg, "message_id", None) or ""
        if not str(mid).strip():
            continue
        eligible.append(msg)

    cap = int(getattr(settings, "DIFY_MARK_INBOUND_READ_MAX_MESSAGES", 0) or 0)
    if cap > 0 and len(eligible) > cap:
        logger.info(
            "[DIFY_WAUX] read receipts limitadas às %s mensagens mais recentes do batch (total=%s)",
            cap,
            len(eligible),
        )
        eligible = eligible[-cap:]

    for msg in eligible:
        try:
            send_read_receipt(
                conversation,
                msg,
                max_retries=2,
                preferred_wa_instance=preferred_wa_instance,
            )
        except Exception as exc:
            logger.warning(
                "[DIFY_WAUX] read receipt falhou msg=%s: %s",
                getattr(msg, "id", "?"),
                exc,
                exc_info=True,
            )
        # Pequeno espaçamento para não martelar Evolution/Meta em batches grandes
        time.sleep(0.08)


def dify_pre_send_outbound_pause(conversation: Any, wa_instance: Any) -> None:
    """
    Envia indicador de digitação (Evolution ou Meta) e aguarda DIFY_PRE_SEND_TYPING_SECONDS
    antes de persistir/enfileirar a resposta ao contato.
    """
    if not getattr(settings, "DIFY_PRE_SEND_TYPING", True):
        return
    if not wa_instance or not conversation:
        return

    phone = (getattr(conversation, "contact_phone", None) or "").strip()
    if not phone:
        return

    seconds = float(getattr(settings, "DIFY_PRE_SEND_TYPING_SECONDS", 1.2) or 1.2)
    seconds = max(0.0, min(seconds, 5.0))

    from apps.notifications.models import WhatsAppInstance

    try:
        if getattr(wa_instance, "integration_type", None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            from apps.notifications.whatsapp_providers import get_sender

            sender = get_sender(wa_instance)
            if sender and hasattr(sender, "send_typing_on"):
                ok, _ = sender.send_typing_on(phone)
                if not ok:
                    logger.warning("[DIFY_WAUX] Meta typing_on não confirmado")
            else:
                logger.debug("[DIFY_WAUX] Meta sender sem send_typing_on")
        else:
            from apps.notifications.whatsapp_evolution_presence import (
                send_evolution_composing_presence,
            )

            send_evolution_composing_presence(conversation, wa_instance, max(seconds, 0.5))
    except Exception as exc:
        logger.warning("[DIFY_WAUX] typing falhou (seguindo envio): %s", exc, exc_info=True)

    if seconds > 0:
        time.sleep(seconds)
