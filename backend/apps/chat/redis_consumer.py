"""
Redis Consumer para Flow Chat.

Processa filas Redis do chat de forma assíncrona.
Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms).
"""
import asyncio
import logging
import redis
from apps.chat.redis_queue import (
    dequeue_message,
    enqueue_dead_letter,
    REDIS_QUEUE_SEND_MESSAGE,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO,
    REDIS_QUEUE_MARK_AS_READ
)
from apps.chat.tasks import (
    handle_send_message,
    handle_fetch_profile_pic,
    handle_mark_message_as_read
)
from apps.chat.media_tasks import handle_fetch_group_info

logger = logging.getLogger(__name__)

# ✅ CORREÇÃO CRÍTICA: Dead-Letter Queue
MAX_RETRIES = 3  # Máximo de tentativas antes de mover para dead-letter


QUEUE_ALIASES = {
    'send_message': 'send_message',
    'fetch_profile_pic': 'fetch_profile_pic',
    'fetch_group_info': 'fetch_group_info',
    'mark_as_read': 'mark_as_read',
}


async def start_redis_consumers(queue_filters: set[str] | None = None):
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - send_message: Enviar mensagem via Evolution API
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
    
    async def process_send_message():
        """Processa fila send_message com retry e dead-letter queue."""
        if queue_filters and 'send_message' not in queue_filters:
            logger.info("⏭️ [REDIS CONSUMER] Fila send_message não selecionada, ignorando.")
            return
        logger.info("📥 [REDIS CONSUMER] Consumer send_message iniciado")
        
        backoff_delay = 1  # Delay inicial para backoff exponencial
        
        while True:
            try:
                # ✅ CORREÇÃO: Tratar timeout vs erro de conexão
                try:
                    payload = dequeue_message(REDIS_QUEUE_SEND_MESSAGE, timeout=5)
                except redis.exceptions.ConnectionError as e:
                    # ✅ CORREÇÃO: Erro de conexão - backoff exponencial
                    logger.warning(f"⚠️ [REDIS CONSUMER] Erro de conexão (send_message): {e}")
                    logger.warning(f"   Aguardando {backoff_delay}s antes de retry...")
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, 60)  # Max 60s
                    continue
                
                # Reset backoff em caso de sucesso
                backoff_delay = 1
                
                if payload:
                    message_id = payload.get('message_id')
                    retry_count = payload.get('_retry_count', 0)
                    
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task send_message: {message_id} (tentativa {retry_count + 1})")
                    
                    try:
                        # Processar mensagem
                        await handle_send_message(message_id)
                        logger.info(f"✅ [REDIS CONSUMER] send_message concluída: {message_id}")
                    except Exception as e:
                        # ✅ CORREÇÃO CRÍTICA: Dead-Letter Queue
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            logger.error(f"❌ [REDIS CONSUMER] send_message falhou após {retry_count} tentativas: {message_id}")
                            enqueue_dead_letter(
                                REDIS_QUEUE_SEND_MESSAGE,
                                payload,
                                str(e),
                                retry_count
                            )
                        else:
                            # Re-enfileirar com retry count incrementado
                            logger.warning(f"⚠️ [REDIS CONSUMER] send_message falhou (tentativa {retry_count}/{MAX_RETRIES}), re-enfileirando...")
                            from apps.chat.redis_queue import enqueue_message
                            payload['_retry_count'] = retry_count
                            enqueue_message(REDIS_QUEUE_SEND_MESSAGE, payload)
                            await asyncio.sleep(1)  # Delay antes de processar próxima mensagem
                else:
                    # Timeout (fila vazia), continuar loop - normal
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                # ✅ Erros inesperados (não timeout) - logar e continuar
                logger.error(f"❌ [REDIS CONSUMER] Erro send_message: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay em caso de erro
    
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
                            from apps.chat.redis_queue import enqueue_message
                            payload['_retry_count'] = retry_count
                            enqueue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, payload)
                            await asyncio.sleep(1)
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
                            from apps.chat.redis_queue import enqueue_message
                            payload['_retry_count'] = retry_count
                            enqueue_message(REDIS_QUEUE_FETCH_GROUP_INFO, payload)
                            await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_group_info: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def process_mark_as_read():
        """Processa fila mark_as_read com retry e dead-letter queue."""
        if queue_filters and 'mark_as_read' not in queue_filters:
            logger.info("⏭️ [REDIS CONSUMER] Fila mark_as_read não selecionada, ignorando.")
            return
        logger.info("📥 [REDIS CONSUMER] Consumer mark_as_read iniciado")
        
        backoff_delay = 1
        
        while True:
            try:
                try:
                    payload = dequeue_message(REDIS_QUEUE_MARK_AS_READ, timeout=5)
                except redis.exceptions.ConnectionError as e:
                    logger.warning(f"⚠️ [REDIS CONSUMER] Erro de conexão (mark_as_read): {e}")
                    logger.warning(f"   Aguardando {backoff_delay}s antes de retry...")
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, 60)
                    continue
                
                backoff_delay = 1
                
                if payload:
                    conversation_id = payload.get('conversation_id')
                    message_id = payload.get('message_id')
                    retry_count = payload.get('_retry_count', 0)
                    
                    if not conversation_id or not message_id:
                        logger.warning(f"⚠️ [REDIS CONSUMER] Payload inválido em mark_as_read: {payload}")
                        continue
                    
                    logger.info(
                        "📥 [REDIS CONSUMER] Recebida task mark_as_read: message=%s conversation=%s (tentativa %s)",
                        message_id,
                        conversation_id,
                        retry_count + 1
                    )
                    
                    try:
                        await handle_mark_message_as_read(conversation_id, message_id)
                        logger.info(
                            "✅ [REDIS CONSUMER] mark_as_read concluída: message=%s conversation=%s",
                            message_id,
                            conversation_id
                        )
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= MAX_RETRIES:
                            logger.error(
                                "❌ [REDIS CONSUMER] mark_as_read falhou após %s tentativas: message=%s conversation=%s",
                                retry_count,
                                message_id,
                                conversation_id
                            )
                            enqueue_dead_letter(
                                REDIS_QUEUE_MARK_AS_READ,
                                payload,
                                str(e),
                                retry_count
                            )
                        else:
                            logger.warning(
                                "⚠️ [REDIS CONSUMER] mark_as_read falhou (tentativa %s/%s), re-enfileirando...",
                                retry_count,
                                MAX_RETRIES
                            )
                            from apps.chat.redis_queue import enqueue_message
                            payload['_retry_count'] = retry_count
                            enqueue_message(REDIS_QUEUE_MARK_AS_READ, payload)
                            await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro mark_as_read: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    # Executar consumers em paralelo
    logger.info("✅ [REDIS CONSUMER] Consumers iniciados!")
    logger.info("=" * 80)
    
    try:
        consumers = []
        if not queue_filters or 'send_message' in queue_filters:
            consumers.append(process_send_message())
        if not queue_filters or 'fetch_profile_pic' in queue_filters:
            consumers.append(process_fetch_profile_pic())
        if not queue_filters or 'fetch_group_info' in queue_filters:
            consumers.append(process_fetch_group_info())
        if not queue_filters or 'mark_as_read' in queue_filters:
            consumers.append(process_mark_as_read())

        if not consumers:
            logger.warning("⚠️ [REDIS CONSUMER] Nenhuma fila ativa configurada. Nada a processar.")
            return

        await asyncio.gather(*consumers)
    except KeyboardInterrupt:
        logger.info("⚠️ [REDIS CONSUMER] Consumers interrompidos pelo usuário")
    except Exception as e:
        logger.error(f"❌ [REDIS CONSUMER] Erro fatal: {e}", exc_info=True)
        raise

