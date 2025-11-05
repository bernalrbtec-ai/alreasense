"""
Redis Queue para Flow Chat.

Usa Redis Database 2 para filas do chat (isolado de cache e channels).
Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms).
"""
import redis
import json
import logging
from datetime import datetime
from threading import Lock
from django.conf import settings

logger = logging.getLogger(__name__)

# Prefixo para filas
QUEUE_PREFIX = "chat:queue:"

# Nomes das filas Redis
REDIS_QUEUE_SEND_MESSAGE = f"{QUEUE_PREFIX}send_message"
REDIS_QUEUE_FETCH_PROFILE_PIC = f"{QUEUE_PREFIX}fetch_profile_pic"
REDIS_QUEUE_FETCH_GROUP_INFO = f"{QUEUE_PREFIX}fetch_group_info"

# ✅ CORREÇÃO CRÍTICA: Dead-Letter Queue
REDIS_QUEUE_DEAD_LETTER = f"{QUEUE_PREFIX}dead_letter"

# ✅ CORREÇÃO CRÍTICA: Singleton para Redis client
_redis_client = None
_redis_lock = Lock()


def get_chat_redis_client():
    """
    Get Redis client for chat queues (Database 2).
    
    ✅ CORREÇÃO CRÍTICA: Singleton pattern para reutilizar conexão.
    Evita criar múltiplas conexões e esgotar pool Redis.
    
    Returns:
        redis.Redis: Redis client ou None se não configurado
    """
    global _redis_client
    
    # ✅ Double-check locking para thread-safety
    if _redis_client is not None:
        try:
            # Testar se conexão ainda está viva
            _redis_client.ping()
            return _redis_client
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            # Conexão morta, recriar
            logger.warning("⚠️ [REDIS] Conexão Redis morta, recriando...")
            _redis_client = None
    
    with _redis_lock:
        # Verificar novamente após adquirir lock
        if _redis_client is not None:
            try:
                _redis_client.ping()
                return _redis_client
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                _redis_client = None
        
        redis_url = settings.REDIS_URL
        
        if not redis_url or redis_url == '':
            logger.warning("⚠️ [REDIS] Redis URL not configured")
            return None
        
        # Usar Database 2 para filas do chat
        # redis://host:port/2
        chat_redis_url = redis_url.replace('/0', '/2')
        
        try:
            _redis_client = redis.Redis.from_url(
                chat_redis_url,
                decode_responses=True,
                max_connections=50,  # Connection pooling
                socket_connect_timeout=10,
                socket_timeout=30,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Testar conexão
            _redis_client.ping()
            logger.info(f"✅ [REDIS] Cliente singleton conectado ao Database 2")
            
            return _redis_client
            
        except Exception as e:
            logger.error(f"❌ [REDIS] Erro ao conectar ao Redis Database 2: {e}", exc_info=True)
            _redis_client = None
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
    
    ✅ CORREÇÃO: Diferenciar timeout normal de erro de conexão.
    
    Args:
        queue_name: Nome da fila
        timeout: Timeout em segundos (0 = sem timeout, None = sem timeout)
    
    Returns:
        dict: Dados da mensagem
        None: Se timeout normal (fila vazia)
        Exception: Se erro de conexão (para retry com backoff)
    
    Raises:
        redis.exceptions.ConnectionError: Se erro de conexão (para diferenciar de timeout)
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível")
            raise redis.exceptions.ConnectionError("Redis client não disponível")
        
        # Desenfileirar mensagem (BRPOP)
        # BRPOP retorna (queue_name, message_json) ou None se timeout
        # ✅ IMPORTANTE: socket_timeout deve ser maior que BRPOP timeout
        result = client.brpop(queue_name, timeout=timeout or 0)
        
        if result is None:
            # ✅ Timeout normal (fila vazia) - não é erro
            return None
        
        # result = (queue_name, message_json)
        _, message_json = result
        payload = json.loads(message_json)
        
        logger.debug(f"✅ [REDIS] Mensagem desenfileirada: {queue_name}")
        logger.debug(f"   Payload keys: {list(payload.keys())}")
        
        return payload
        
    except redis.exceptions.TimeoutError as e:
        # ✅ Timeout é normal quando fila está vazia (não é erro crítico)
        logger.debug(f"⏱️ [REDIS] Timeout ao desenfileirar (fila vazia): {queue_name}")
        return None
        
    except redis.exceptions.ConnectionError as e:
        # ✅ CORREÇÃO: Erro de conexão - re-raise para diferenciar de timeout
        # Permite que consumer implemente backoff exponencial
        logger.warning(f"⚠️ [REDIS] Erro de conexão ao desenfileirar: {e}")
        raise  # Re-raise para diferenciar de timeout
        
    except Exception as e:
        # ✅ Outros erros - logar como erro e re-raise
        logger.error(f"❌ [REDIS] Erro ao desenfileirar mensagem: {e}", exc_info=True)
        raise


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


# ✅ CORREÇÃO CRÍTICA: Dead-Letter Queue
def enqueue_dead_letter(queue_name: str, payload: dict, error: str, retry_count: int):
    """
    Move mensagem para dead-letter queue após N tentativas falhadas.
    
    Args:
        queue_name: Nome da fila original
        payload: Dados da mensagem que falhou
        error: Mensagem de erro
        retry_count: Número de tentativas realizadas
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            logger.error("❌ [REDIS] Redis client não disponível para dead-letter")
            return
        
        dead_letter_payload = {
            'original_queue': queue_name,
            'payload': payload,
            'error': error,
            'retry_count': retry_count,
            'failed_at': json.dumps(datetime.now().isoformat())
        }
        
        message = json.dumps(dead_letter_payload)
        client.lpush(REDIS_QUEUE_DEAD_LETTER, message)
        
        logger.warning(f"⚠️ [REDIS] Mensagem movida para dead-letter: {queue_name} (tentativas: {retry_count})")
        logger.warning(f"   Erro: {error}")
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao mover para dead-letter: {e}", exc_info=True)


def get_queue_metrics():
    """
    ✅ CORREÇÃO: Métricas e monitoramento de filas.
    
    Returns:
        dict: Métricas de todas as filas
    """
    try:
        client = get_chat_redis_client()
        if client is None:
            return {}
        
        metrics = {
            'send_message': {
                'length': client.llen(REDIS_QUEUE_SEND_MESSAGE),
                'name': REDIS_QUEUE_SEND_MESSAGE
            },
            'fetch_profile_pic': {
                'length': client.llen(REDIS_QUEUE_FETCH_PROFILE_PIC),
                'name': REDIS_QUEUE_FETCH_PROFILE_PIC
            },
            'fetch_group_info': {
                'length': client.llen(REDIS_QUEUE_FETCH_GROUP_INFO),
                'name': REDIS_QUEUE_FETCH_GROUP_INFO
            },
            'dead_letter': {
                'length': client.llen(REDIS_QUEUE_DEAD_LETTER),
                'name': REDIS_QUEUE_DEAD_LETTER
            },
            'total': 0
        }
        
        metrics['total'] = sum(q['length'] for q in metrics.values() if isinstance(q, dict))
        
        return metrics
        
    except Exception as e:
        logger.error(f"❌ [REDIS] Erro ao obter métricas: {e}", exc_info=True)
        return {}

