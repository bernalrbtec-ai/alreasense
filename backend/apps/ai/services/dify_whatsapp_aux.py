"""
Sinais auxiliares no fluxo Dify + WhatsApp — **Evolution API e Meta Cloud API**.

- **Lido (read):** `send_read_receipt` → Evolution `markMessageAsRead` ou Meta Graph `mark_as_read`.
- **Digitando (typing):** Evolution `POST /chat/sendPresence` (`send_evolution_composing_presence`);
  Meta Graph `typing_indicator` + `message_id` com fallback `typing_on` (`MetaCloudProvider.send_typing_on`).

O mesmo código é usado para ambos os providers; o ramo escolhe-se por `WhatsAppInstance.integration_type`
(`None`/evolution → Evolution; `meta_cloud` → Meta), alinhado a `get_sender`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterable, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _eligible_inbound_messages_for_wa_aux(messages: Optional[Iterable[Any]]) -> list:
    """
    Mensagens inbound com `message_id` (Evolution/Meta), não apagadas, na ordem do iterável.
    Usado para reads e para escolher o último id (âncora typing Meta) — uma única regra.
    """
    if not messages:
        return []
    out: list = []
    for msg in messages:
        if msg is None:
            continue
        if getattr(msg, "direction", "") != "incoming":
            continue
        if getattr(msg, "is_deleted", False):
            continue
        mid = str(getattr(msg, "message_id", None) or "").strip()
        if not mid:
            continue
        out.append(msg)
    return out


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

    eligible = _eligible_inbound_messages_for_wa_aux(messages)

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


def _last_inbound_whatsapp_message_id(messages: Optional[Iterable[Any]]) -> str:
    """
    Último `message_id` inbound (wamid na Meta, id Evolution no payload de read) — usado como
    âncora do typing na **Meta**; na **Evolution** o typing usa só o telefone/JID (este valor é ignorado).
    """
    eligible = _eligible_inbound_messages_for_wa_aux(messages)
    if not eligible:
        return ""
    return str(getattr(eligible[-1], "message_id", None) or "").strip()


def dify_pre_send_outbound_pause(
    conversation: Any,
    wa_instance: Any,
    last_inbound_wa_message_id: str = "",
) -> None:
    """
    Envia indicador de digitação e aguarda `DIFY_PRE_SEND_TYPING_SECONDS` antes de gravar/enfileirar a resposta.

    - **Evolution:** `sendPresence` / composing (não usa `last_inbound_wa_message_id`).
    - **Meta Cloud:** `typing_indicator` com esse wamid quando existir; senão `typing_on` por número.
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
        integration = getattr(wa_instance, "integration_type", None) or WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION
        if integration == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            from apps.notifications.whatsapp_providers import get_sender

            sender = get_sender(wa_instance)
            if sender and hasattr(sender, "send_typing_on"):
                anchor = (last_inbound_wa_message_id or "").strip()
                ok, _ = sender.send_typing_on(
                    phone, inbound_message_id=anchor if anchor else None
                )
                if not ok:
                    logger.warning(
                        "[DIFY_WAUX] Meta typing não confirmado (anchor_len=%s)",
                        len(anchor),
                    )
                elif not anchor:
                    logger.info(
                        "[DIFY_WAUX] Meta typing via action (sem wamid anchor); "
                        "se não aparecer no cliente, garantir inbound_messages_for_receipt na thread Dify",
                    )
            else:
                logger.debug("[DIFY_WAUX] Meta sender sem send_typing_on")
        else:
            from apps.notifications.whatsapp_evolution_presence import (
                send_evolution_composing_presence,
            )

            evo_ok = send_evolution_composing_presence(
                conversation, wa_instance, max(seconds, 0.5)
            )
            if not evo_ok:
                logger.warning(
                    "[DIFY_WAUX] Evolution composing não confirmado (inst=%s)",
                    getattr(wa_instance, "id", "?"),
                )
    except Exception as exc:
        logger.warning("[DIFY_WAUX] typing falhou (seguindo envio): %s", exc, exc_info=True)

    if seconds > 0:
        time.sleep(seconds)
