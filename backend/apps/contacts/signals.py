"""
Signals para atualizar métricas de contatos automaticamente e sincronizar com conversas
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def get_contact_model():
    """Lazy import para evitar circular imports"""
    from apps.contacts.models import Contact
    return Contact


@receiver(post_save)
def update_conversations_on_contact_change(sender, instance, created, **kwargs):
    """
    Quando um contato é criado ou atualizado:
    1. Invalidar cache de contact_tags nas conversas relacionadas
    2. Atualizar conversas relacionadas via WebSocket broadcast
    """
    # Verificar se é o modelo Contact
    Contact = get_contact_model()
    if not isinstance(instance, Contact):
        return
    
    from apps.chat.models import Conversation
    from apps.chat.utils.websocket import broadcast_conversation_updated
    
    # Invalidar cache de contact_tags para este contato
    cache_key = f"contact_tags:{instance.tenant_id}:{instance.phone}"
    cache.delete(cache_key)
    logger.info(f"🗑️ [CONTACT SIGNAL] Cache invalidado: {cache_key}")
    
    # Buscar todas as conversas relacionadas a este telefone no mesmo tenant
    conversations = Conversation.objects.filter(
        tenant=instance.tenant,
        contact_phone=instance.phone,
        conversation_type='individual'  # Apenas conversas individuais têm contatos
    )
    
    if conversations.exists():
        logger.info(f"🔄 [CONTACT SIGNAL] Atualizando {conversations.count()} conversa(s) para contato {instance.phone}")
        
        # Atualizar cada conversa e fazer broadcast
        for conversation in conversations:
            try:
                # Fazer broadcast da conversa atualizada (serializer vai buscar tags atualizadas)
                broadcast_conversation_updated(conversation)
                logger.debug(f"✅ [CONTACT SIGNAL] Broadcast enviado para conversa {conversation.id}")
            except Exception as e:
                logger.error(f"❌ [CONTACT SIGNAL] Erro ao fazer broadcast para conversa {conversation.id}: {e}", exc_info=True)
    else:
        logger.debug(f"ℹ️ [CONTACT SIGNAL] Nenhuma conversa encontrada para telefone {instance.phone}")


@receiver(post_delete)
def update_conversations_on_contact_delete(sender, instance, **kwargs):
    """
    Quando um contato é deletado:
    1. Invalidar cache de contact_tags
    2. Atualizar conversas relacionadas (tags serão removidas automaticamente pelo serializer)
    """
    # Verificar se é o modelo Contact
    Contact = get_contact_model()
    if not isinstance(instance, Contact):
        return
    
    from apps.chat.models import Conversation
    from apps.chat.utils.websocket import broadcast_conversation_updated
    
    # Invalidar cache
    cache_key = f"contact_tags:{instance.tenant_id}:{instance.phone}"
    cache.delete(cache_key)
    logger.info(f"🗑️ [CONTACT SIGNAL] Cache invalidado após deleção: {cache_key}")
    
    # Buscar conversas relacionadas
    conversations = Conversation.objects.filter(
        tenant=instance.tenant,
        contact_phone=instance.phone,
        conversation_type='individual'
    )
    
    if conversations.exists():
        logger.info(f"🔄 [CONTACT SIGNAL] Atualizando {conversations.count()} conversa(s) após deleção do contato")
        
        for conversation in conversations:
            try:
                broadcast_conversation_updated(conversation)
                logger.debug(f"✅ [CONTACT SIGNAL] Broadcast enviado para conversa {conversation.id} após deleção")
            except Exception as e:
                logger.error(f"❌ [CONTACT SIGNAL] Erro ao fazer broadcast após deleção: {e}", exc_info=True)
