"""
Utilitários para WebSocket broadcasts no sistema de chat.

Centraliza a lógica de broadcast para evitar duplicação de código
nos views, webhooks e consumers.
"""
import logging
from typing import Any, Dict, Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def broadcast_to_tenant(tenant_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """
    Envia broadcast para todos os usuários de um tenant.
    
    Args:
        tenant_id: UUID do tenant
        event_type: Tipo do evento (ex: 'conversation_updated', 'message_received')
        data: Dados do evento (deve ser serializável para JSON)
    
    Example:
        broadcast_to_tenant(
            tenant_id=str(conversation.tenant_id),
            event_type='conversation_updated',
            data={'conversation': conv_data}
        )
    """
    from apps.chat.utils.serialization import convert_uuids_to_str
    
    channel_layer = get_channel_layer()
    tenant_group = f"chat_tenant_{tenant_id}"
    
    # Garantir que UUIDs são convertidos para string
    serializable_data = convert_uuids_to_str(data)
    
    message = {
        'type': event_type,
        **serializable_data
    }
    
    try:
        async_to_sync(channel_layer.group_send)(tenant_group, message)
        logger.debug(f"📡 [WEBSOCKET] Broadcast enviado: {event_type} para tenant {tenant_id}")
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao enviar broadcast: {e}", exc_info=True)


def broadcast_conversation_updated(conversation) -> None:
    """
    Broadcast específico para quando uma conversa é atualizada.
    
    Usado após:
    - Marcar mensagens como lidas
    - Atualizar metadados da conversa
    - Mudar status/atendente
    
    Args:
        conversation: Instância do modelo Conversation
    """
    from apps.chat.api.serializers import ConversationSerializer
    
    conv_data = ConversationSerializer(conversation).data
    
    broadcast_to_tenant(
        tenant_id=str(conversation.tenant_id),
        event_type='conversation_updated',
        data={'conversation': conv_data}
    )
    
    logger.info(f"📡 [WEBSOCKET] Conversa {conversation.id} atualizada via broadcast")


def broadcast_message_received(message) -> None:
    """
    Broadcast específico para quando uma nova mensagem é recebida.
    
    Usado após:
    - Webhook messages.upsert
    - Mensagem criada via API
    
    Args:
        message: Instância do modelo Message
    """
    from apps.chat.api.serializers import MessageSerializer
    
    msg_data = MessageSerializer(message).data
    
    broadcast_to_tenant(
        tenant_id=str(message.conversation.tenant_id),
        event_type='message_received',
        data={
            'message': msg_data,
            'conversation_id': str(message.conversation_id)
        }
    )
    
    logger.info(f"📡 [WEBSOCKET] Mensagem {message.id} broadcast para tenant")


def broadcast_message_status_update(message) -> None:
    """
    Broadcast específico para atualização de status de mensagem.
    
    Usado após:
    - Webhook messages.update (sent → delivered → seen)
    - Status atualizado localmente
    
    Args:
        message: Instância do modelo Message
    """
    broadcast_to_tenant(
        tenant_id=str(message.conversation.tenant_id),
        event_type='message_status_update',
        data={
            'message_id': str(message.id),
            'conversation_id': str(message.conversation_id),
            'status': message.status,
            'evolution_status': message.evolution_status
        }
    )
    
    logger.debug(
        f"📡 [WEBSOCKET] Status {message.status} broadcast para "
        f"mensagem {message.id}"
    )


def broadcast_typing_indicator(conversation_id: str, tenant_id: str, 
                               user_name: str, is_typing: bool) -> None:
    """
    Broadcast para indicador de digitação.
    
    Args:
        conversation_id: UUID da conversa
        tenant_id: UUID do tenant
        user_name: Nome do usuário digitando
        is_typing: True se começou a digitar, False se parou
    """
    broadcast_to_tenant(
        tenant_id=tenant_id,
        event_type='typing_indicator',
        data={
            'conversation_id': conversation_id,
            'user_name': user_name,
            'is_typing': is_typing
        }
    )
    
    action = "digitando" if is_typing else "parou de digitar"
    logger.debug(f"📡 [WEBSOCKET] {user_name} {action} em {conversation_id}")


def broadcast_conversation_assigned(conversation, old_user, new_user) -> None:
    """
    Broadcast quando uma conversa é atribuída/reatribuída.
    
    Args:
        conversation: Instância do modelo Conversation
        old_user: Usuário anterior (pode ser None)
        new_user: Novo usuário (pode ser None)
    """
    from apps.chat.api.serializers import ConversationSerializer
    
    conv_data = ConversationSerializer(conversation).data
    
    broadcast_to_tenant(
        tenant_id=str(conversation.tenant_id),
        event_type='conversation_assigned',
        data={
            'conversation': conv_data,
            'old_user_id': str(old_user.id) if old_user else None,
            'new_user_id': str(new_user.id) if new_user else None,
            'old_user_name': old_user.get_full_name() if old_user else None,
            'new_user_name': new_user.get_full_name() if new_user else None,
        }
    )
    
    logger.info(
        f"📡 [WEBSOCKET] Conversa {conversation.id} atribuída: "
        f"{old_user} → {new_user}"
    )

