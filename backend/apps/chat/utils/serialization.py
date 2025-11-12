"""
Utilitários para serialização de dados no sistema de chat.

Centraliza conversão de tipos não serializáveis (UUID, datetime, etc)
e normalização de metadata para evitar duplicação de código.
"""
import uuid
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Union


def convert_uuids_to_str(obj: Any) -> Any:
    """
    Converte recursivamente UUIDs para strings em objetos Python.
    
    Também converte outros tipos não serializáveis para JSON:
    - datetime → ISO 8601 string
    - date → ISO 8601 string  
    - Decimal → float
    - set → list
    
    Args:
        obj: Objeto Python (dict, list, UUID, datetime, etc)
        
    Returns:
        Objeto com todos os UUIDs convertidos para strings
        
    Example:
        >>> data = {
        ...     'id': UUID('123e4567-e89b-12d3-a456-426614174000'),
        ...     'created_at': datetime.now(),
        ...     'nested': {
        ...         'user_id': UUID('...'),
        ...         'items': [UUID('...'), UUID('...')]
        ...     }
        ... }
        >>> convert_uuids_to_str(data)
        {
            'id': '123e4567-e89b-12d3-a456-426614174000',
            'created_at': '2025-01-27T10:30:00.123456',
            'nested': {
                'user_id': '...',
                'items': ['...', '...']
            }
        }
    """
    # UUID → string
    if isinstance(obj, uuid.UUID):
        return str(obj)
    
    # datetime/date → ISO 8601 string
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Decimal → float (para JSON)
    if isinstance(obj, Decimal):
        return float(obj)
    
    # set → list (JSON não tem set)
    if isinstance(obj, set):
        return [convert_uuids_to_str(item) for item in obj]
    
    # dict → recursivo
    if isinstance(obj, dict):
        return {key: convert_uuids_to_str(value) for key, value in obj.items()}
    
    # list/tuple → recursivo
    if isinstance(obj, (list, tuple)):
        return [convert_uuids_to_str(item) for item in obj]
    
    # Outros tipos → retornar como está
    return obj


def serialize_for_websocket(data: Union[Dict, List]) -> Union[Dict, List]:
    """
    Prepara dados para envio via WebSocket.
    
    Alias para convert_uuids_to_str com nome mais explícito.
    Use quando for enviar dados via channel_layer.group_send().
    
    Args:
        data: Dict ou List com dados a serem serializados
        
    Returns:
        Dados serializáveis para JSON (sem UUIDs, datetimes, etc)
        
    Example:
        >>> from channels.layers import get_channel_layer
        >>> from asgiref.sync import async_to_sync
        >>> 
        >>> channel_layer = get_channel_layer()
        >>> data = serialize_for_websocket({'user_id': user.id, 'created_at': now()})
        >>> async_to_sync(channel_layer.group_send)(
        ...     'group_name',
        ...     {'type': 'message', **data}
        ... )
    """
    return convert_uuids_to_str(data)


def serialize_conversation_for_ws(conversation) -> Dict[str, Any]:
    """
    Serializa uma conversa completa para WebSocket.
    
    ⚠️ ATENÇÃO: Esta função é SÍNCRONA e faz queries ao banco.
    Use serialize_conversation_for_ws_async() em contextos assíncronos.
    
    Args:
        conversation: Instância do modelo Conversation
    
    Returns:
        Dict serializável para JSON com todos os dados da conversa
    """
    from apps.chat.api.serializers import ConversationSerializer
    
    conv_data = ConversationSerializer(conversation).data
    return convert_uuids_to_str(conv_data)


async def serialize_conversation_for_ws_async(conversation) -> Dict[str, Any]:
    """
    Serializa uma conversa completa para WebSocket em contexto assíncrono.
    
    ✅ Use esta função em funções async (tasks, consumers, etc).
    
    Args:
        conversation: Instância do modelo Conversation
    
    Returns:
        Dict serializável para JSON com todos os dados da conversa
    """
    from apps.chat.api.serializers import ConversationSerializer
    from asgiref.sync import sync_to_async
    
    # ✅ Serializar em thread separada para evitar SynchronousOnlyOperation
    serializer = ConversationSerializer(conversation)
    conv_data = await sync_to_async(lambda: serializer.data)()
    return convert_uuids_to_str(conv_data)


def serialize_message_for_ws(message) -> Dict[str, Any]:
    """
    Serializa uma mensagem completa para WebSocket.
    
    ✅ CORREÇÃO: Prefetch de reações para evitar race conditions.
    ✅ CORREÇÃO: Garantir que attachments também estão prefetched.
    ✅ CORREÇÃO: Não fazer refetch se mensagem já tem dados necessários (evita problemas de sincronização).
    
    Args:
        message: Instância do modelo Message
    
    Returns:
        Dict serializável para JSON com todos os dados da mensagem
    """
    from apps.chat.api.serializers import MessageSerializer
    from apps.chat.models import Message
    
    # ✅ CORREÇÃO: Prefetch de reações e attachments se ainda não foi feito
    # Mas apenas se realmente necessário (evitar refetch desnecessário que pode causar problemas)
    needs_refetch = False
    prefetch_cache = getattr(message, '_prefetched_objects_cache', {})
    
    # Verificar se precisa de refetch apenas se não tiver prefetch cache ou se cache está vazio
    if not prefetch_cache:
        needs_refetch = True
    else:
        if 'reactions' not in prefetch_cache:
            needs_refetch = True
        if 'attachments' not in prefetch_cache:
            needs_refetch = True
    
    # ✅ CORREÇÃO: Fazer refetch apenas se realmente necessário e se mensagem já foi salva
    if needs_refetch and message.pk:
        try:
            # Recarregar mensagem com prefetch completo
            message = Message.objects.prefetch_related(
                'reactions__user',
                'attachments'
            ).select_related(
                'sender',
                'conversation'
            ).get(id=message.id)
        except Message.DoesNotExist:
            # Se mensagem não existe mais, usar a original (pode ser mensagem ainda não salva)
            pass
    
    msg_data = MessageSerializer(message).data
    return convert_uuids_to_str(msg_data)


def prepare_ws_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara um evento completo para WebSocket com type + data.
    
    Args:
        event_type: Nome do handler no consumer (ex: 'message_received')
        data: Dados do evento
        
    Returns:
        Dict pronto para channel_layer.group_send()
        
    Example:
        >>> event = prepare_ws_event('message_received', {
        ...     'message': message_data,
        ...     'conversation_id': conv_id
        ... })
        >>> async_to_sync(channel_layer.group_send)(group, event)
    """
    serialized_data = convert_uuids_to_str(data)
    return {
        'type': event_type,
        **serialized_data
    }


def normalize_metadata(metadata: Any) -> Dict[str, Any]:
    """
    Normaliza metadata para garantir que sempre seja dict.
    
    Converte:
    - None → {}
    - str (JSON) → dict (parseado)
    - dict → dict (mantém)
    - Outros tipos → {}
    
    Args:
        metadata: dict, str (JSON), None ou qualquer outro tipo
        
    Returns:
        dict: Metadata normalizado (sempre dict)
        
    Example:
        >>> normalize_metadata(None)
        {}
        >>> normalize_metadata('{"key": "value"}')
        {'key': 'value'}
        >>> normalize_metadata({'key': 'value'})
        {'key': 'value'}
        >>> normalize_metadata('invalid json')
        {}
    """
    if metadata is None:
        return {}
    
    if isinstance(metadata, str):
        try:
            return json.loads(metadata) if metadata else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    
    if isinstance(metadata, dict):
        return metadata
    
    # Outros tipos → dict vazio
    return {}

