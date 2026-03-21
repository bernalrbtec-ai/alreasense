"""
Signals para o módulo Flow Chat.
"""
import logging
import time

from django.db import connection, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.chat.models import Conversation, Message

logger = logging.getLogger(__name__)

DIFY_EPISODE_META_KEY = "dify_episode_id"


@receiver(post_save, sender=Message)
def log_message_created(sender, instance, created, **kwargs):
    """Log quando uma mensagem é criada."""
    if created:
        direction_emoji = "📩" if instance.direction == 'incoming' else "📨"
        logger.info(
            f"{direction_emoji} [CHAT] Nova mensagem: {instance.conversation.contact_phone} "
            f"- {instance.content[:50] if instance.content else '[sem texto]'}"
        )


@receiver(pre_save, sender=Conversation)
def _dify_capture_prev_conversation_status(sender, instance, **kwargs):
    """Guarda status anterior para detectar reabertura (closed → aberto/pending)."""
    if not instance.pk:
        instance._dify_prev_status = None
        return
    try:
        instance._dify_prev_status = (
            Conversation.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )
    except Exception:
        instance._dify_prev_status = None


@receiver(post_save, sender=Conversation)
def on_conversation_dify_episode(sender, instance, created, **kwargs):
    """
    Cada episódio (abertura inicial ou reabertura após closed) recebe dify_episode_id (ms UTC).

    O Dify usa `user` = sense:tenant:agent:phone:episode — novo episódio => nova conversa no Dify.
    Ao reabrir, limpa dify_conversation_id persistido em ai_dify_conversation_state.
    """
    if created:
        md = dict(instance.metadata or {})
        if not (md.get(DIFY_EPISODE_META_KEY) or "").strip():
            md[DIFY_EPISODE_META_KEY] = str(int(time.time() * 1000))
            Conversation.objects.filter(pk=instance.pk).update(metadata=md)
            instance.metadata = md
        return

    prev = getattr(instance, "_dify_prev_status", None)
    if prev == "closed" and instance.status != "closed":
        new_ep = str(int(time.time() * 1000))
        md = dict(instance.metadata or {})
        md[DIFY_EPISODE_META_KEY] = new_ep
        Conversation.objects.filter(pk=instance.pk).update(metadata=md)
        instance.metadata = md
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE ai_dify_conversation_state SET dify_conversation_id = NULL, updated_at = NOW() "
                    "WHERE conversation_id = %s AND tenant_id = %s",
                    [str(instance.pk), str(instance.tenant_id)],
                )
        except Exception as exc:
            logger.warning(
                "⚠️ [DIFY] episódio: limpar dify_conversation_id falhou conv=%s: %s",
                instance.pk,
                exc,
            )
        logger.info(
            "🔄 [DIFY] Novo episódio após reabertura conv=%s episode=%s",
            instance.pk,
            new_ep,
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

