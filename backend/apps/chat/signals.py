"""
Signals para o módulo Flow Chat.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.chat.models import Message, Conversation

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


@receiver(post_save, sender=Conversation)
def on_conversation_closed_start_summary_pipeline(sender, instance, created, **kwargs):
    """
    Ao fechar conversa (status=closed), dispara pipeline de resumo em background (summarize → rag-upsert).
    BIA: resumos são gravados no pgvector para a BIA usar quando o contato voltar.
    Idempotência: se metadata.conversation_summary_at já existir, não dispara.
    Grupos (g.us) são ignorados. Só dispara se o tenant tiver TenantSecretaryProfile com use_memory=True.
    Se N8N_SUMMARIZE_WEBHOOK_URL estiver vazio, o pipeline sai sem exceção. Rag-upsert é feito só ao aprovar na gestão RAG.
    """
    if created:
        return
    if instance.status != "closed":
        return
    metadata = instance.metadata or {}
    if metadata.get("conversation_summary_at"):
        return
    if "g.us" in (instance.contact_phone or ""):
        return
    # Pipeline de resumos descontinuado: não disparar mais resumos ao fechar conversa.
    return

