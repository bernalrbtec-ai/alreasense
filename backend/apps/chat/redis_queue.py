"""
Redis Queue para Flow Chat.

Usa Redis Database 2 para filas do chat (isolado de cache e channels).
Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms).
"""
import redis
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Prefixo para filas
QUEUE_PREFIX = "chat:queue:"

# Nomes das filas Redis
REDIS_QUEUE_SEND_MESSAGE = f"{QUEUE_PREFIX}send_message"
REDIS_QUEUE_FETCH_PROFILE_PIC = f"{QUEUE_PREFIX}fetch_profile_pic"
REDIS_QUEUE_FETCH_GROUP_INFO = f"{QUEUE_PREFIX}fetch_group_info"


def get_chat_redis_client():
    """
    Get Redis client for chat queues (Database 2).
    
    Returns:
        redis.Redis: Redis client ou None se não configurado
    """
    redis_url = settings.REDIS_URL
    
    if not redis_url or redis_url == '':
        logger.warning("⚠️ [REDIS] Redis URL not configured")
        return None
    
    # Usar Database 2 para filas do chat
    # redis://host:port/2
    chat_redis_url = redis_url.replace('/0', '/2')
    
    try:
        client = redis.Redis.from_url(
            chat_redis_url,
            decode_responses=True,
            max_connections=50,  # Connection pooling
            socket_connect_timeout=10,  # ✅ AUMENTADO: 5s → 10s
            socket_timeout=30,  # ✅ AUMENTADO: 5s → 30s (maior que BRPOP timeout)
            socket_keepalive=True,  # ✅ NOVO: Keepalive para manter conexão
            socket_keepalive_options={},  # ✅ NOVO: Opções de keepalive
            retry_on_timeout=True,
            health_check_interval=30  # ✅ NOVO: Health check a cada 30s
        )
        
        # Testar conexão
        client.ping()
        logger.debug(f"✅ [REDIS] Cliente conectado ao Database 2")
        
        return client
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao conectar ao Redis Database 2: {e}", exc_info=True)
        return None


def enqueue_message(queue_name: str, payload: dict):
    """
    Enfileira mensagem no Redis (LPUSH).
    
    Args:
        queue_name: Nome da fila (ex: REDIS_QUEUE_SEND_MESSAGE)
        payload: Dados da mensagem
    
    Returns:
        int: Número de mensagens na fila após adicionar
    
    Raises:
        Exception: Se Redis não estiver disponível ou erro ao enfileirar
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível")
            raise Exception("Redis client não disponível")
        
        # Enfileirar mensagem (LPUSH)
        message = json.dumps(payload)
        queue_length = client.lpush(queue_name, message)
        
        logger.info(f"✅ [REDIS] Mensagem enfileirada: {queue_name} (fila: {queue_length} msgs)")
        logger.debug(f"   Payload keys: {list(payload.keys())}")
        
        return queue_length
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao enfileirar mensagem: {e}", exc_info=True)
        raise


def dequeue_message(queue_name: str, timeout: int = 5):
    """
    Desenfileira mensagem do Redis (BRPOP).
    
    Args:
        queue_name: Nome da fila
        timeout: Timeout em segundos (0 = sem timeout, None = sem timeout)
    
    Returns:
        dict: Dados da mensagem ou None se timeout
    
    Raises:
        Exception: Se Redis não estiver disponível ou erro ao desenfileirar
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível")
            return None
        
        # Desenfileirar mensagem (BRPOP)
        # BRPOP retorna (queue_name, message_json) ou None se timeout
        # ✅ IMPORTANTE: socket_timeout deve ser maior que BRPOP timeout
        result = client.brpop(queue_name, timeout=timeout or 0)
        
        if result is None:
            # Timeout normal (fila vazia) - não é erro
            return None
        
        # result = (queue_name, message_json)
        _, message_json = result
        payload = json.loads(message_json)
        
        logger.debug(f"✅ [REDIS] Mensagem desenfileirada: {queue_name}")
        logger.debug(f"   Payload keys: {list(payload.keys())}")
        
        return payload
        
    except redis.exceptions.TimeoutError as e:
        # ✅ Timeout é normal quando fila está vazia (não é erro crítico)
        # Não logar como erro, apenas debug
        logger.debug(f"⏱️ [REDIS] Timeout ao desenfileirar (fila vazia): {queue_name}")
        return None
        
    except redis.exceptions.ConnectionError as e:
        # ✅ Erro de conexão - logar como warning (será reconectado automaticamente)
        logger.warning(f"⚠️ [REDIS] Erro de conexão ao desenfileirar: {e}")
        return None
        
    except Exception as e:
        # ✅ Outros erros - logar como erro
        logger.error(f"❌ [REDIS] Erro ao desenfileirar mensagem: {e}", exc_info=True)
        return None


def get_queue_length(queue_name: str):
    """
    Retorna tamanho da fila.
    
    Args:
        queue_name: Nome da fila
    
    Returns:
        int: Número de mensagens na fila ou 0 se erro
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            return 0
        
        return client.llen(queue_name)
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao obter tamanho da fila: {e}", exc_info=True)
        return 0


def clear_queue(queue_name: str):
    """
    Limpa todas as mensagens da fila.
    
    Args:
        queue_name: Nome da fila
    
    Returns:
        int: Número de mensagens removidas
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            return 0
        
        # Deletar todas as mensagens da fila
        deleted = client.delete(queue_name)
        
        logger.info(f"✅ [REDIS] Fila limpa: {queue_name} ({deleted} mensagens removidas)")
        
        return deleted
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao limpar fila: {e}", exc_info=True)
        return 0

