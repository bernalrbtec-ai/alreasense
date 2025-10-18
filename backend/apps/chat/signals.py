"""
Signals para o módulo Flow Chat.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.chat.models import Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def log_message_created(sender, instance, created, **kwargs):
    """Log quando uma mensagem é criada."""
    if created:
        direction_emoji = "📩" if instance.direction == 'incoming' else "📨"
        logger.info(
            f"{direction_emoji} [CHAT] Nova mensagem: {instance.conversation.contact_phone} "
            f"- {instance.content[:50] if instance.content else '[sem texto]'}"
        )

