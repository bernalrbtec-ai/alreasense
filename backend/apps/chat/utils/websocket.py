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


def broadcast_conversation_updated(conversation, request=None) -> None:
    """
    Broadcast específico para quando uma conversa é atualizada.
    
    Usado após:
    - Marcar mensagens como lidas
    - Atualizar metadados da conversa
    - Mudar status/atendente
    - Nova mensagem recebida (para atualizar unread_count e last_message_at)
    
    Args:
        conversation: Instância do modelo Conversation
        request: Objeto request (opcional, para contexto do serializer)
    """
    from apps.chat.api.serializers import ConversationSerializer
    from django.db.models import Count, Q
    from apps.chat.models import Message
    
    # ✅ FIX CRÍTICO: SEMPRE recalcular unread_count para garantir que está atualizado
    # Isso garante que o unread_count sempre esteja correto mesmo quando a conversa vem direto do modelo
    # Recarregar do banco para garantir dados atualizados
    conversation.refresh_from_db()
    
    # Buscar conversa com annotate para garantir unread_count correto
    from apps.chat.models import Conversation
    from django.db.models import Prefetch
    conversation_with_annotate = Conversation.objects.annotate(
        unread_count_annotated=Count(
            'messages',
            filter=Q(
                messages__direction='incoming',
                messages__status__in=['sent', 'delivered']
            ),
            distinct=True
        )
    ).prefetch_related(
        Prefetch(
            'messages',
            queryset=Message.objects.select_related('sender', 'conversation')
                .prefetch_related('attachments')
                .order_by('-created_at')[:1],
            to_attr='last_message_list'
        )
    ).get(id=conversation.id)
    
    # ✅ FIX CRÍTICO: Transferir annotate E prefetch para o objeto original
    # Isso garante que o serializer tenha acesso ao last_message_list
    conversation.unread_count_annotated = conversation_with_annotate.unread_count_annotated
    
    # ✅ FIX CRÍTICO: Transferir last_message_list do prefetch para o objeto original
    # O serializer precisa deste atributo para retornar last_message corretamente
    if hasattr(conversation_with_annotate, 'last_message_list'):
        conversation.last_message_list = conversation_with_annotate.last_message_list
    
    # ✅ CORREÇÃO CRÍTICA: Garantir que last_message_list sempre tenha dados
    # Se prefetch falhar ou não retornar nada, buscar última mensagem diretamente
    if not hasattr(conversation, 'last_message_list') or not conversation.last_message_list:
        # Fallback: buscar última mensagem diretamente
        last_msg = Message.objects.filter(
            conversation=conversation
        ).select_related('sender', 'conversation').prefetch_related('attachments').order_by('-created_at').first()
        
        if last_msg:
            conversation.last_message_list = [last_msg]
            logger.debug(f"📨 [WEBSOCKET] Fallback: última mensagem buscada diretamente para conversa {conversation.id}")
        else:
            # Se realmente não há mensagens, criar lista vazia
            conversation.last_message_list = []
            logger.debug(f"📭 [WEBSOCKET] Nenhuma mensagem encontrada para conversa {conversation.id}")
    
    # ✅ FIX: Garantir que last_message_at está atualizado (vem do banco após refresh_from_db)
    # Não precisa fazer nada extra, refresh_from_db já atualiza last_message_at
    
    # Serializar com contexto se disponível
    # ✅ IMPORTANTE: Usar conversation (que agora tem last_message_list) ao invés de conversation_with_annotate
    serializer_context = {'request': request} if request else {}
    conv_data = ConversationSerializer(conversation, context=serializer_context).data
    
    broadcast_to_tenant(
        tenant_id=str(conversation.tenant_id),
        event_type='conversation_updated',
        data={'conversation': conv_data}
    )
    
    logger.info(f"📡 [WEBSOCKET] Conversa {conversation.id} atualizada via broadcast (unread_count: {conv_data.get('unread_count', 'N/A')}, last_message_at: {conv_data.get('last_message_at', 'N/A')})")


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


def broadcast_message_deleted(message) -> None:
    """
    Broadcast quando uma mensagem é apagada no WhatsApp.
    
    Args:
        message: Instância do modelo Message que foi apagada
    """
    from apps.chat.utils.serialization import serialize_message_for_ws
    
    conversation = message.conversation
    tenant_id = str(conversation.tenant_id)
    conversation_id = str(conversation.id)
    
    # Serializar mensagem
    message_data = serialize_message_for_ws(message)
    
    # Broadcast para conversa específica
    room_group_name = f"chat_tenant_{tenant_id}_conversation_{conversation_id}"
    broadcast_to_tenant(
        tenant_id=tenant_id,
        event_type='message_deleted',
        data={
            'message': message_data,
            'conversation_id': conversation_id
        }
    )
    
    # Também enviar para grupo da conversa específica
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_deleted',
                'message': message_data
            }
        )
        logger.info(f"🗑️ [WEBSOCKET] Broadcast de mensagem apagada enviado: {message.id}")
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao enviar broadcast de mensagem apagada: {e}", exc_info=True)


def broadcast_message_reaction_update(message, reaction_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Broadcast quando uma reação é adicionada ou removida de uma mensagem.
    
    ✅ CORREÇÃO CRÍTICA: Broadcast para tenant inteiro (não apenas conversa específica).
    Isso garante que todos os usuários vejam atualizações de reações em tempo real.
    
    Usado após:
    - Adicionar reação (POST /chat/reactions/add/)
    - Remover reação (POST /chat/reactions/remove/)
    
    Args:
        message: Instância do modelo Message (com reações prefetched)
        reaction_data: Dados opcionais da reação (emoji, user, removed, etc)
    """
    from apps.chat.utils.serialization import serialize_message_for_ws
    
    # ✅ CORREÇÃO: Garantir que mensagem tem reações prefetched antes de serializar
    # serialize_message_for_ws já faz isso, mas garantimos aqui também
    from apps.chat.models import Message
    if not hasattr(message, '_prefetched_objects_cache') or 'reactions' not in getattr(message, '_prefetched_objects_cache', {}):
        message = Message.objects.prefetch_related('reactions__user').get(id=message.id)
    
    # Serializar mensagem completa com reações atualizadas
    message_data = serialize_message_for_ws(message)
    
    # Preparar dados do broadcast
    broadcast_data = {
        'message': message_data,
        'conversation_id': str(message.conversation_id)
    }
    
    # Adicionar dados da reação se fornecidos
    if reaction_data:
        broadcast_data['reaction'] = reaction_data
    
    # ✅ CORREÇÃO CRÍTICA: Broadcast para tenant inteiro (não apenas conversa específica)
    # Isso garante que todos os usuários vejam atualizações de reações
    broadcast_to_tenant(
        tenant_id=str(message.conversation.tenant_id),
        event_type='message_reaction_update',
        data=broadcast_data
    )
    
    logger.info(
        f"📡 [WEBSOCKET] Reação atualizada para mensagem {message.id} "
        f"(tenant: {message.conversation.tenant_id})"
    )

