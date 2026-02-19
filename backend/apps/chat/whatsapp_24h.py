"""
Janela de 24h para WhatsApp (Meta Cloud API).
Regra: apenas mensagens INBOUND do contato renovam a janela.
Mensagens de saída (template ou texto livre) NÃO abrem/renovam a janela.
"""
import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from .models import Conversation, Message

logger = logging.getLogger(__name__)

WINDOW_HOURS = 24


def get_last_inbound_at(conversation: Conversation):
    """
    Retorna o created_at da última mensagem INCOMING da conversa.
    Apenas mensagens do contato (inbound) contam para a janela de 24h.
    """
    last = (
        Message.objects.filter(
            conversation=conversation,
            direction='incoming',
            is_internal=False,
        )
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )
    return last


def is_within_24h_window(conversation: Conversation) -> bool:
    """
    Verifica se a conversa está dentro da janela de 24h para envio de texto livre (Meta).
    Considera apenas a última mensagem INBOUND do contato (não mensagens nossas/template).
    """
    last_inbound = get_last_inbound_at(conversation)
    if last_inbound is None:
        return False
    now = timezone.now()
    if timezone.is_naive(last_inbound):
        last_inbound = timezone.make_aware(last_inbound)
    threshold = now - timedelta(hours=WINDOW_HOURS)
    within = last_inbound >= threshold
    if not within:
        logger.debug(
            "[24h] Fora da janela conversation_id=%s last_inbound=%s threshold=%s",
            str(conversation.id),
            last_inbound,
            threshold,
        )
    return within
