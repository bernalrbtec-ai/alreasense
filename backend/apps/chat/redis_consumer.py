"""
Redis Consumer para Flow Chat.

Processa filas Redis do chat de forma assíncrona.
Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms).
"""
import asyncio
import logging
from apps.chat.redis_queue import (
    dequeue_message,
    REDIS_QUEUE_SEND_MESSAGE,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO
)
from apps.chat.tasks import (
    handle_send_message,
    handle_fetch_profile_pic
)
from apps.chat.media_tasks import handle_fetch_group_info

logger = logging.getLogger(__name__)


async def start_redis_consumers():
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - send_message: Enviar mensagem via Evolution API
    - fetch_profile_pic: Buscar foto de perfil
    - fetch_group_info: Buscar info de grupo
    """
    logger.info("=" * 80)
    logger.info("🚀 [REDIS CONSUMER] Iniciando consumers Redis do chat...")
    logger.info("=" * 80)
    
    async def process_send_message():
        """Processa fila send_message."""
        logger.info("📥 [REDIS CONSUMER] Consumer send_message iniciado")
        
        while True:
            try:
                # Desenfileirar mensagem (timeout 5s)
                payload = dequeue_message(REDIS_QUEUE_SEND_MESSAGE, timeout=5)
                
                if payload:
                    message_id = payload.get('message_id')
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task send_message: {message_id}")
                    
                    # Processar mensagem
                    await handle_send_message(message_id)
                    
                    logger.info(f"✅ [REDIS CONSUMER] send_message concluída: {message_id}")
                else:
                    # Timeout (fila vazia), continuar loop
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro send_message: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay em caso de erro
    
    async def process_fetch_profile_pic():
        """Processa fila fetch_profile_pic."""
        logger.info("📥 [REDIS CONSUMER] Consumer fetch_profile_pic iniciado")
        
        while True:
            try:
                # Desenfileirar mensagem (timeout 5s)
                payload = dequeue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, timeout=5)
                
                if payload:
                    conversation_id = payload.get('conversation_id')
                    phone = payload.get('phone')
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_profile_pic: {conversation_id}")
                    
                    # Processar busca de foto
                    await handle_fetch_profile_pic(conversation_id, phone)
                    
                    logger.info(f"✅ [REDIS CONSUMER] fetch_profile_pic concluída: {conversation_id}")
                else:
                    # Timeout (fila vazia), continuar loop
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_profile_pic: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay em caso de erro
    
    async def process_fetch_group_info():
        """Processa fila fetch_group_info."""
        logger.info("📥 [REDIS CONSUMER] Consumer fetch_group_info iniciado")
        
        while True:
            try:
                # Desenfileirar mensagem (timeout 5s)
                payload = dequeue_message(REDIS_QUEUE_FETCH_GROUP_INFO, timeout=5)
                
                if payload:
                    conversation_id = payload.get('conversation_id')
                    logger.info(f"📥 [REDIS CONSUMER] Recebida task fetch_group_info: {conversation_id}")
                    
                    # Processar busca de info de grupo
                    await handle_fetch_group_info(
                        payload['conversation_id'],
                        payload['group_jid'],
                        payload['instance_name'],
                        payload['api_key'],
                        payload['base_url']
                    )
                    
                    logger.info(f"✅ [REDIS CONSUMER] fetch_group_info concluída: {conversation_id}")
                else:
                    # Timeout (fila vazia), continuar loop
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ [REDIS CONSUMER] Erro fetch_group_info: {e}", exc_info=True)
                await asyncio.sleep(1)  # Delay em caso de erro
    
    # Executar consumers em paralelo
    logger.info("✅ [REDIS CONSUMER] Consumers iniciados!")
    logger.info("=" * 80)
    
    try:
        await asyncio.gather(
            process_send_message(),
            process_fetch_profile_pic(),
            process_fetch_group_info()
        )
    except KeyboardInterrupt:
        logger.info("⚠️ [REDIS CONSUMER] Consumers interrompidos pelo usuário")
    except Exception as e:
        logger.error(f"❌ [REDIS CONSUMER] Erro fatal: {e}", exc_info=True)
        raise

