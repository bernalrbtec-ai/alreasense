"""
Signals para o módulo Flow Chat.
"""
import logging
from django.db import transaction
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
    Ao fechar conversa (status=closed), dispara ingestão de transcript textual (sem anexos) para RAG
    quando o agente Dify do escopo (assignment) tiver rag_enabled no catálogo.

    Grupos WhatsApp (g.us) são ignorados.
    Se metadata.conversation_summary_at estiver definido, não dispara (legado / compatibilidade).
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
    # Pipeline de resumos descontinuado.
    # Novo fluxo: ingestão textual (sem anexos) para memória RAG do Dify.
    try:
        from apps.ai.services.dify_rag_memory_service import launch_ingest_closed_conversation

        transaction.on_commit(lambda: launch_ingest_closed_conversation(str(instance.id)))
    except Exception as exc:
        logger.warning(
            "RAG ingest trigger failed for conversation %s: %s",
            str(instance.id),
            exc,
            exc_info=True,
        )

