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


def send_user_notification(
    tenant_id: str,
    target_user_id: str,
    notification_type: str,
    data: Dict[str, Any],
) -> None:
    """
    Envia notificação para um usuário específico via canal do chat (chat_tenant_{id}).
    O frontend filtra por target_user_id e exibe toast/sino apenas para o usuário alvo.

    Args:
        tenant_id: UUID do tenant
        target_user_id: ID do usuário alvo (string)
        notification_type: 'conversation_transferred' | 'task_reminder' | 'agenda_reminder'
        data: Dados da notificação (conversation_id, conversation, message, task_id, etc.)
    """
    payload = {
        "target_user_id": str(target_user_id),
        "notification_type": notification_type,
        **data,
    }
    broadcast_to_tenant(tenant_id, "user_notification", payload)
    logger.debug(
        f"📡 [WEBSOCKET] user_notification enviado: {notification_type} para user {target_user_id}"
    )


def broadcast_conversation_updated(conversation, request=None, message_id=None) -> None:
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
        message_id: ID da mensagem recém-criada (opcional, para garantir que seja incluída no last_message)
    """
    from apps.chat.api.serializers import ConversationSerializer
    from django.db.models import Count, Q
    from apps.chat.models import Message
    
    # ✅ NOTA: Esta função assume que já está sendo chamada APÓS commit da transação
    # (via transaction.on_commit() nos chamadores). Não tenta gerenciar transações aqui.
    # Se message_id foi fornecido, a mensagem já deve estar commitada quando esta função é chamada.
    
    # ✅ FIX CRÍTICO: SEMPRE recalcular unread_count para garantir que está atualizado
    # Isso garante que o unread_count sempre esteja correto mesmo quando a conversa vem direto do modelo
    # Recarregar do banco para garantir dados atualizados
    conversation.refresh_from_db()
    
    # ✅ CORREÇÃO CRÍTICA: Buscar última mensagem de forma mais robusta
    # Se message_id foi fornecido, garantir que essa mensagem seja incluída
    last_message_queryset = Message.objects.filter(
        is_deleted=False
    ).select_related('sender', 'conversation').prefetch_related('attachments').order_by('-created_at')
    
    # Se temos message_id, garantir que essa mensagem seja incluída (pode ser a mais recente)
    if message_id:
        # Buscar a mensagem específica primeiro para garantir que está disponível
        try:
            specific_message = Message.objects.select_related('sender', 'conversation').prefetch_related('attachments').get(id=message_id)
            # Usar essa mensagem como última se for a mais recente
            last_msg = last_message_queryset.filter(conversation=conversation).first()
            if last_msg and str(last_msg.id) == str(message_id):
                # A mensagem específica é realmente a última, usar ela
                conversation.last_message_list = [specific_message]
                logger.debug(f"📨 [WEBSOCKET] Usando mensagem específica {message_id} como last_message")
            else:
                # Buscar normalmente, mas garantir que a mensagem específica está incluída se for mais recente
                conversation.last_message_list = [last_msg] if last_msg else []
        except Message.DoesNotExist:
            # Mensagem ainda não está disponível, buscar normalmente
            last_msg = last_message_queryset.filter(conversation=conversation).first()
            conversation.last_message_list = [last_msg] if last_msg else []
    else:
        # Buscar normalmente sem message_id específico
        last_msg = last_message_queryset.filter(conversation=conversation).first()
        conversation.last_message_list = [last_msg] if last_msg else []
    
    # Buscar conversa com annotate para garantir unread_count correto
    from apps.chat.models import Conversation
    from django.db.models import Prefetch
    conversation_with_annotate = Conversation.objects.annotate(
        unread_count_annotated=Count(
            'messages',
            filter=Q(
                messages__direction='incoming',
                messages__status__in=['sent', 'delivered'],
                messages__is_deleted=False
            ),
            distinct=True
        )
    ).get(id=conversation.id)
    
    # ✅ FIX CRÍTICO: Transferir annotate para o objeto original
    conversation.unread_count_annotated = conversation_with_annotate.unread_count_annotated
    
    # ✅ CORREÇÃO CRÍTICA: Se não temos last_message_list ainda, buscar do prefetch
    # Mas priorizar a mensagem que já buscamos acima (pode ser mais recente)
    if not hasattr(conversation, 'last_message_list') or not conversation.last_message_list:
        # Fallback: buscar última mensagem diretamente
        last_msg = Message.objects.filter(
            conversation=conversation,
            is_deleted=False
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
    serializer_context = {'request': request} if request else {}
    conv_data = ConversationSerializer(conversation, context=serializer_context).data
    
    # ✅ LOG CRÍTICO: Verificar se last_message está incluído
    last_message_in_data = conv_data.get('last_message')
    logger.info(f"📡 [WEBSOCKET] Conversa {conversation.id} atualizada via broadcast")
    logger.info(f"   unread_count: {conv_data.get('unread_count', 'N/A')}")
    logger.info(f"   last_message_at: {conv_data.get('last_message_at', 'N/A')}")
    logger.info(f"   last_message presente: {last_message_in_data is not None}")
    if last_message_in_data:
        logger.info(f"   last_message content: {last_message_in_data.get('content', 'N/A')[:50]}...")
    
    # ✅ LOG CRÍTICO: Verificar department e status sendo enviado
    logger.critical(f"📋 [WEBSOCKET] Dados sendo enviados no broadcast:")
    logger.critical(f"   conversation_id: {conv_data.get('id', 'N/A')}")
    logger.critical(f"   department (UUID): {conv_data.get('department')}")
    logger.critical(f"   department_name: {conv_data.get('department_name', 'N/A')}")
    logger.critical(f"   status: {conv_data.get('status', 'N/A')}")
    logger.critical(f"   contact_name: {conv_data.get('contact_name', 'N/A')}")
    logger.critical(f"   contact_phone: {conv_data.get('contact_phone', 'N/A')}")
    logger.critical(f"   last_message_at: {conv_data.get('last_message_at', 'N/A')}")
    logger.critical(f"   last_message presente: {conv_data.get('last_message') is not None}")
    
    # ✅ VALIDAÇÃO CRÍTICA: Se status é 'closed', logar como WARNING
    if conv_data.get('status') == 'closed':
        logger.warning(f"⚠️ [WEBSOCKET] ATENÇÃO: Conversa {conv_data.get('id')} está sendo enviada com status='closed'!")
        logger.warning(f"   Isso pode fazer a conversa não aparecer na lista!")
        logger.warning(f"   Verifique se a conversa deveria estar fechada.")
    
    broadcast_to_tenant(
        tenant_id=str(conversation.tenant_id),
        event_type='conversation_updated',
        data={'conversation': conv_data}
    )


def broadcast_message_received(message) -> None:
    """
    Broadcast específico para quando uma nova mensagem é recebida.
    Inclui a conversa no payload para o frontend poder adicionar/atualizar e abrir quando apropriado.
    
    Usado após:
    - Webhook messages.upsert
    - Mensagem criada via API
    
    Args:
        message: Instância do modelo Message
    """
    from apps.chat.api.serializers import MessageSerializer, ConversationSerializer
    
    msg_data = MessageSerializer(message).data
    conv = message.conversation
    # Incluir conversa para o frontend adicionar ao store e poder abrir (ex.: conversa nova via webhook Meta)
    conv_data = None
    try:
        # Garantir last_message para o serializer (evita query extra). Restaurar depois para não mutar o modelo.
        prev_list = getattr(conv, 'last_message_list', None)
        if not prev_list:
            conv.last_message_list = [message]
        try:
            conv_data = ConversationSerializer(conv).data
        finally:
            if not prev_list:
                conv.last_message_list = prev_list
    except Exception as e:
        logger.warning("📡 [WEBSOCKET] Não foi possível serializar conversa em message_received: %s", e)
    
    data = {
        'message': msg_data,
        'conversation_id': str(conv.id),
    }
    if conv_data:
        data['conversation'] = conv_data
    
    broadcast_to_tenant(
        tenant_id=str(conv.tenant_id),
        event_type='message_received',
        data=data,
    )
    
    logger.info(f"📡 [WEBSOCKET] Mensagem {message.id} broadcast para tenant")


def broadcast_message_status_update(message) -> None:
    """
    Broadcast específico para atualização de status de mensagem.
    Envia para o tenant e para a room da conversa (chat aberto).
    Usado após:
    - Webhook messages.update (sent → delivered → seen)
    - Status atualizado localmente (Evolution ou Meta)
    """
    from apps.chat.utils.serialization import convert_uuids_to_str

    data = {
        'message_id': str(message.id),
        'conversation_id': str(message.conversation_id),
        'status': message.status,
        'evolution_status': message.evolution_status,
    }
    if message.status == 'failed':
        meta = getattr(message, 'metadata', None) or {}
        if meta.get('can_use_fallback'):
            data['send_error_meta'] = {
                'can_use_fallback': True,
                'fallback_instance_friendly_name': meta.get('fallback_instance_friendly_name'),
                'unavailable_instance_friendly_name': meta.get('unavailable_instance_friendly_name'),
            }
    data = convert_uuids_to_str(data)
    payload = {'type': 'message_status_update', **data}

    channel_layer = get_channel_layer()
    tenant_group = f"chat_tenant_{message.conversation.tenant_id}"
    room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
    try:
        async_to_sync(channel_layer.group_send)(tenant_group, payload)
        async_to_sync(channel_layer.group_send)(room_group_name, payload)
        logger.debug(
            "📡 [WEBSOCKET] Status %s broadcast para mensagem %s (tenant + room)",
            message.status,
            message.id,
        )
    except Exception as e:
        logger.error("❌ [WEBSOCKET] Erro ao enviar broadcast message_status_update: %s", e, exc_info=True)


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
                'message': message_data,
                'message_id': str(message.id),
                'conversation_id': conversation_id
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

