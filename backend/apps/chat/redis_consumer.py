"""
Redis Consumer para Flow Chat.

Processa filas Redis do chat de forma assíncrona.
Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms).
"""
import asyncio
import logging
import time

import redis
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.chat.redis_queue import (
    dequeue_message,
    enqueue_dead_letter,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO,
)
from apps.chat.tasks import (
    handle_fetch_profile_pic,
)
from apps.chat.media_tasks import handle_fetch_group_info
from apps.chat.utils.metrics import update_worker_heartbeat, record_latency

logger = logging.getLogger(__name__)

# ✅ CORREÇÃO CRÍTICA: Dead-Letter Queue
MAX_RETRIES = 3  # Máximo de tentativas antes de mover para dead-letter

_pending_requeues: set[asyncio.Task] = set()


def _schedule_requeue(queue_name: str, payload: dict, delay_seconds: float = 0.0) -> None:
    """
    Reenfileira payload sem bloquear o worker. Mantém referência para evitar GC.
    """
    async def _requeue():
        try:
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            from apps.chat.redis_queue import enqueue_message  # lazy import to avoid cycles
            payload['enqueued_at'] = timezone.now().isoformat()
            enqueue_message(queue_name, payload)
        except Exception:
            logger.exception("❌ [REDIS CONSUMER] Falha ao reenfileirar payload %s", queue_name)
        finally:
            _pending_requeues.discard(task)

    task = asyncio.create_task(_requeue())
    _pending_requeues.add(task)


QUEUE_ALIASES = {
    'fetch_profile_pic': 'fetch_profile_pic',
    'fetch_group_info': 'fetch_group_info',
}


async def start_redis_consumers(queue_filters: set[str] | None = None):
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - fetch_profile_pic: Buscar foto de perfil
    - fetch_group_info: Buscar info de grupo
    """
    logger.info("=" * 80)
    if queue_filters:
        logger.info("🚀 [REDIS CONSUMER] Iniciando consumers Redis do chat (filtrados: %s)...", ', '.join(sorted(queue_filters)))
        normalized_filters = {QUEUE_ALIASES.get(q.lower(), q.lower()) for q in queue_filters}
        queue_filters = normalized_filters
    else:
        logger.info("🚀 [REDIS CONSUMER] Iniciando consumers Redis do chat (todas as filas)...")
        queue_filters = None
    logger.info("=" * 80)
    
    async def process_fetch_profile_pic():
        """Processa fila fetch_profile_pic com retry e dead-letter queue."""
        if queue_filters and 'fetch_profile_pic' not in queue_filters:
            logger.info("⏭️ [REDIS CONSUMER] Fila fetch_profile_pic não selecionada, ignorando.")
            return
        logger.info("📥 [REDIS CONSUMER] Consumer fetch_profile_pic iniciado")
        
        backoff_delay = 1
        
        while True:
            try:
                try:
                    payload = dequeue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, timeout=5)
                except redis.exceptions.ConnectionError as e:
                    logger.warning(f"⚠️ [REDIS CONSUMER] Erro de conexão (fetch_profile_pic): {e}")
                    logger.warning(f"   Aguardando {backoff_delay}s antes de retry...")
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, 60)
                    continue
                
                backoff_delay = 1
                
                if payload:
                    conversation_id = payload.get('conversation_id')
                    phone = payload.get('phone')
                    retry_count = payload.get('_retry_count', 0)
                    
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_profile_pic: {conversation_id} (tentativa {retry_count + 1})")
                    
                    try:
                        await handle_fetch_profile_pic(conversation_id, phone)
                        logger.info(f"✅ [REDIS CONSUMER] fetch_profile_pic concluída: {conversation_id}")
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            logger.error(f"❌ [REDIS CONSUMER] fetch_profile_pic falhou após {retry_count} tentativas: {conversation_id}")
                            enqueue_dead_letter(
                                REDIS_QUEUE_FETCH_PROFILE_PIC,
                                payload,
                                str(e),
                                retry_count
                            )
                        else:
                            logger.warning(f"⚠️ [REDIS CONSUMER] fetch_profile_pic falhou (tentativa {retry_count}/{MAX_RETRIES}), re-enfileirando...")
                            payload['_retry_count'] = retry_count
                            _schedule_requeue(REDIS_QUEUE_FETCH_PROFILE_PIC, payload, delay_seconds=1)
                else:
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_profile_pic: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def process_fetch_group_info():
        """Processa fila fetch_group_info com retry e dead-letter queue."""
        if queue_filters and 'fetch_group_info' not in queue_filters:
            logger.info("⏭️ [REDIS CONSUMER] Fila fetch_group_info não selecionada, ignorando.")
            return
        logger.info("📥 [REDIS CONSUMER] Consumer fetch_group_info iniciado")
        
        backoff_delay = 1
        
        while True:
            try:
                try:
                    payload = dequeue_message(REDIS_QUEUE_FETCH_GROUP_INFO, timeout=5)
                except redis.exceptions.ConnectionError as e:
                    logger.warning(f"⚠️ [REDIS CONSUMER] Erro de conexão (fetch_group_info): {e}")
                    logger.warning(f"   Aguardando {backoff_delay}s antes de retry...")
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, 60)
                    continue
                
                backoff_delay = 1
                
                if payload:
                    conversation_id = payload.get('conversation_id')
                    retry_count = payload.get('_retry_count', 0)
                    
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_group_info: {conversation_id} (tentativa {retry_count + 1})")
                    
                    try:
                        await handle_fetch_group_info(
                            payload['conversation_id'],
                            payload['group_jid'],
                            payload['instance_name'],
                            payload['api_key'],
                            payload['base_url']
                        )
                        logger.info(f"✅ [REDIS CONSUMER] fetch_group_info concluída: {conversation_id}")
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            logger.error(f"❌ [REDIS CONSUMER] fetch_group_info falhou após {retry_count} tentativas: {conversation_id}")
                            enqueue_dead_letter(
                                REDIS_QUEUE_FETCH_GROUP_INFO,
                                payload,
                                str(e),
                                retry_count
                            )
                        else:
                            logger.warning(f"⚠️ [REDIS CONSUMER] fetch_group_info falhou (tentativa {retry_count}/{MAX_RETRIES}), re-enfileirando...")
                            payload['_retry_count'] = retry_count
                            _schedule_requeue(REDIS_QUEUE_FETCH_GROUP_INFO, payload, delay_seconds=1)
                else:
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_group_info: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    # Executar consumers em paralelo
    logger.info("✅ [REDIS CONSUMER] Consumers iniciados!")
    logger.info("=" * 80)
    
    try:
        consumers = []
        if not queue_filters or 'fetch_profile_pic' in queue_filters:
            consumers.append(process_fetch_profile_pic())
        if not queue_filters or 'fetch_group_info' in queue_filters:
            consumers.append(process_fetch_group_info())
        if not consumers:
            logger.warning("⚠️ [REDIS CONSUMER] Nenhuma fila ativa configurada. Nada a processar.")
            return

        await asyncio.gather(*consumers)
    except KeyboardInterrupt:
        logger.info("⚠️ [REDIS CONSUMER] Consumers interrompidos pelo usuário")
    except Exception as e:
        logger.error(f"❌ [REDIS CONSUMER] Erro fatal: {e}", exc_info=True)
        raise

