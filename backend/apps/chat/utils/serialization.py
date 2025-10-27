"""
Utilitários para serialização de dados no sistema de chat.

Centraliza conversão de tipos não serializáveis (UUID, datetime, etc)
para evitar duplicação de código.
"""
import uuid
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
    
    Args:
        conversation: Instância do modelo Conversation
        
    Returns:
        Dict serializável para JSON com todos os dados da conversa
    """
    from apps.chat.api.serializers import ConversationSerializer
    
    conv_data = ConversationSerializer(conversation).data
    return convert_uuids_to_str(conv_data)


def serialize_message_for_ws(message) -> Dict[str, Any]:
    """
    Serializa uma mensagem completa para WebSocket.
    
    Args:
        message: Instância do modelo Message
        
    Returns:
        Dict serializável para JSON com todos os dados da mensagem
    """
    from apps.chat.api.serializers import MessageSerializer
    
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

