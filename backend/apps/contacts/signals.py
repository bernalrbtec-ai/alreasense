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


def normalize_phone_for_search(phone: str) -> str:
    """
    Normaliza telefone para busca (remove formatação, garante formato E.164).
    Usado para encontrar conversas mesmo com pequenas diferenças de formatação.
    """
    if not phone:
        return phone
    
    # Remover formatação (parênteses, hífens, espaços, @s.whatsapp.net)
    clean = phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
    clean = ''.join(c for c in clean if c.isdigit() or c == '+')
    
    # Garantir formato E.164 (com +)
    if clean and not clean.startswith('+'):
        # Se começa com 55, adicionar +
        if clean.startswith('55'):
            clean = '+' + clean
        else:
            # Assumir Brasil (+55)
            clean = '+55' + clean
    
    return clean


@receiver(post_save)
def update_conversations_on_contact_change(sender, instance, created, **kwargs):
    """
    Quando um contato é criado ou atualizado:
    1. Invalidar cache de contact_tags nas conversas relacionadas
    2. Atualizar contact_name das conversas com o nome do contato
    3. Atualizar conversas relacionadas via WebSocket broadcast
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
    
    # Normalizar telefone do contato para busca
    normalized_contact_phone = normalize_phone_for_search(instance.phone)
    
    # Buscar todas as conversas relacionadas a este telefone no mesmo tenant
    # ✅ CORREÇÃO: Buscar por telefone normalizado para encontrar todas as variações
    conversations = Conversation.objects.filter(
        tenant=instance.tenant,
        conversation_type='individual'  # Apenas conversas individuais têm contatos
    )
    
    # Filtrar conversas que correspondem ao telefone (normalizando para comparação)
    matching_conversations = []
    for conv in conversations:
        normalized_conv_phone = normalize_phone_for_search(conv.contact_phone)
        if normalized_conv_phone == normalized_contact_phone:
            matching_conversations.append(conv)
    
    if matching_conversations:
        logger.info(f"🔄 [CONTACT SIGNAL] Atualizando {len(matching_conversations)} conversa(s) para contato {instance.phone}")
        
        # Atualizar cada conversa com nome do contato e fazer broadcast
        for conversation in matching_conversations:
            try:
                # ✅ CORREÇÃO CRÍTICA: Atualizar contact_name da conversa com nome do contato
                # Isso resolve o problema de conversas aparecendo com número ao invés do nome
                needs_update = False
                update_fields = []
                
                # Atualizar nome se diferente
                if conversation.contact_name != instance.name:
                    conversation.contact_name = instance.name
                    update_fields.append('contact_name')
                    needs_update = True
                    logger.info(f"📝 [CONTACT SIGNAL] Atualizando contact_name: '{conversation.contact_name}' → '{instance.name}'")
                
                # Se telefone da conversa está diferente (formatação), atualizar também
                if conversation.contact_phone != instance.phone:
                    conversation.contact_phone = instance.phone
                    update_fields.append('contact_phone')
                    needs_update = True
                    logger.info(f"📞 [CONTACT SIGNAL] Atualizando contact_phone: '{conversation.contact_phone}' → '{instance.phone}'")
                
                # Salvar se houver mudanças
                if needs_update:
                    conversation.save(update_fields=update_fields)
                    logger.info(f"✅ [CONTACT SIGNAL] Conversa {conversation.id} atualizada: {', '.join(update_fields)}")
                
                # Fazer broadcast da conversa atualizada (serializer vai buscar tags atualizadas)
                broadcast_conversation_updated(conversation)
                logger.debug(f"✅ [CONTACT SIGNAL] Broadcast enviado para conversa {conversation.id}")
            except Exception as e:
                logger.error(f"❌ [CONTACT SIGNAL] Erro ao fazer broadcast para conversa {conversation.id}: {e}", exc_info=True)
    else:
        logger.debug(f"ℹ️ [CONTACT SIGNAL] Nenhuma conversa encontrada para telefone {instance.phone} (normalizado: {normalized_contact_phone})")


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
