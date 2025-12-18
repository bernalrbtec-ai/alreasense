"""
Publisher RabbitMQ para sistema de Billing
Publica mensagens nas filas de billing para processamento assíncrono
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from django.conf import settings
import aio_pika
import re

logger = logging.getLogger(__name__)


class BillingQueuePublisher:
    """
    Publisher para publicar mensagens de billing no RabbitMQ.
    Usa aio-pika para operações assíncronas.
    """
    
    # Nomes das filas por tipo de template
    QUEUE_OVERDUE = 'billing.overdue'
    QUEUE_UPCOMING = 'billing.upcoming'
    QUEUE_NOTIFICATION = 'billing.notification'
    
    # Exchange principal
    EXCHANGE_NAME = 'billing'
    
    @staticmethod
    def publish_queue_sync(queue_id: str, template_type: str) -> bool:
        """
        Versão síncrona de publish_queue para uso em código síncrono.
        
        Args:
            queue_id: ID da BillingQueue (UUID string)
            template_type: Tipo de template ('overdue', 'upcoming', 'notification')
        
        Returns:
            True se publicado com sucesso, False caso contrário
        """
        import asyncio
        import threading
        import queue as thread_queue
        
        result_queue = thread_queue.Queue()
        
        def run_async():
            """Executa função assíncrona em novo event loop"""
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(
                        BillingQueuePublisher.publish_queue(queue_id, template_type)
                    )
                    result_queue.put(('success', result))
                finally:
                    new_loop.close()
            except Exception as e:
                result_queue.put(('error', e))
        
        # Verifica se já há um event loop rodando
        try:
            loop = asyncio.get_running_loop()
            # Se há loop rodando, executa em thread separada
            thread = threading.Thread(target=run_async, daemon=True)
            thread.start()
            thread.join(timeout=5)  # Timeout de 5 segundos
            
            if not result_queue.empty():
                status, result = result_queue.get()
                if status == 'error':
                    logger.error(f"Erro ao publicar queue: {result}", exc_info=True)
                    return False
                return result
            else:
                logger.warning("Timeout ao publicar no RabbitMQ (será processado depois)")
                return False
        except RuntimeError:
            # Não há loop rodando, pode usar asyncio.run() normalmente
            try:
                return asyncio.run(
                    BillingQueuePublisher.publish_queue(queue_id, template_type)
                )
            except Exception as e:
                logger.error(f"Erro ao publicar queue: {e}", exc_info=True)
                return False
    
    @staticmethod
    async def publish_queue(queue_id: str, template_type: str) -> bool:
        """
        Publica uma queue de billing no RabbitMQ para processamento.
        
        Args:
            queue_id: ID da BillingQueue (UUID string)
            template_type: Tipo de template ('overdue', 'upcoming', 'notification')
        
        Returns:
            True se publicado com sucesso, False caso contrário
        """
        try:
            # Mapeia template_type para nome da fila
            queue_map = {
                'overdue': BillingQueuePublisher.QUEUE_OVERDUE,
                'upcoming': BillingQueuePublisher.QUEUE_UPCOMING,
                'notification': BillingQueuePublisher.QUEUE_NOTIFICATION,
            }
            
            queue_name = queue_map.get(template_type)
            if not queue_name:
                logger.error(f"❌ [BILLING_PUBLISHER] Tipo de template inválido: {template_type}")
                return False
            
            # Payload da mensagem
            payload = {
                'queue_id': queue_id,
                'template_type': template_type,
                'timestamp': None  # Será preenchido no publish
            }
            
            # Publica na fila
            success = await BillingQueuePublisher._publish_message(queue_name, payload)
            
            if success:
                logger.info(
                    f"✅ [BILLING_PUBLISHER] Queue {queue_id} publicada na fila '{queue_name}' "
                    f"(tipo: {template_type})"
                )
            else:
                logger.error(f"❌ [BILLING_PUBLISHER] Falha ao publicar queue {queue_id}")
            
            return success
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_PUBLISHER] Erro ao publicar queue {queue_id}: {e}",
                exc_info=True
            )
            return False
    
    @staticmethod
    async def _publish_message(queue_name: str, payload: Dict[str, Any]) -> bool:
        """
        Publica mensagem no RabbitMQ usando aio-pika.
        
        Args:
            queue_name: Nome da fila
            payload: Dados da mensagem
        
        Returns:
            True se publicado com sucesso
        """
        connection = None
        try:
            # ✅ SECURITY: Não usar credenciais hardcoded
            rabbitmq_url = settings.RABBITMQ_URL
            
            # Log seguro (mascarar credenciais)
            safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)
            logger.debug(f"🔍 [BILLING_PUBLISHER] Conectando ao RabbitMQ: {safe_url}")
            
            # Conecta ao RabbitMQ
            connection = await aio_pika.connect_robust(
                rabbitmq_url,
                heartbeat=0,
                blocked_connection_timeout=0,
                socket_timeout=10,
                retry_delay=1,
                connection_attempts=1
            )
            
            # Cria channel
            channel = await connection.channel()
            
            # Configura QoS (prefetch_count=1 para processar uma mensagem por vez)
            await channel.set_qos(prefetch_count=1)
            
            # Declara exchange (se não existir)
            exchange = await channel.declare_exchange(
                BillingQueuePublisher.EXCHANGE_NAME,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Declara fila (se não existir)
            queue = await channel.declare_queue(queue_name, durable=True)
            
            # Bind fila ao exchange
            await queue.bind(exchange, routing_key=queue_name)
            
            # Adiciona timestamp ao payload
            from django.utils import timezone
            payload['timestamp'] = timezone.now().isoformat()
            
            # Publica mensagem
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Persistir mensagem
                timestamp=int(timezone.now().timestamp())
            )
            
            await exchange.publish(
                message,
                routing_key=queue_name
            )
            
            logger.debug(f"📤 [BILLING_PUBLISHER] Mensagem publicada na fila '{queue_name}'")
            
            # Fecha channel (não fecha connection para reutilização)
            await channel.close()
            
            return True
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_PUBLISHER] Erro ao publicar mensagem na fila '{queue_name}': {e}",
                exc_info=True
            )
            return False
            
        finally:
            # Fecha connection se ainda estiver aberta
            if connection and not connection.is_closed:
                try:
                    await connection.close()
                except:
                    pass
    
    @staticmethod
    async def publish_retry(contact_id: str, template_type: str, retry_count: int) -> bool:
        """
        Publica uma mensagem para retry na fila de retry.
        
        Args:
            contact_id: ID do BillingContact
            template_type: Tipo de template
            retry_count: Número da tentativa de retry
        
        Returns:
            True se publicado com sucesso
        """
        try:
            queue_name = f'billing.retry.{template_type}'
            
            payload = {
                'contact_id': contact_id,
                'template_type': template_type,
                'retry_count': retry_count,
                'timestamp': None
            }
            
            return await BillingQueuePublisher._publish_message(queue_name, payload)
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_PUBLISHER] Erro ao publicar retry para contact {contact_id}: {e}",
                exc_info=True
            )
            return False


