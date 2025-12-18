"""
Consumer RabbitMQ com aio-pika - Sistema de Billing
Processa filas de billing de forma assíncrona e robusta
"""
import asyncio
import json
import logging
import threading
from typing import Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import aio_pika
import re

from apps.billing.billing_api import (
    BillingQueue, BillingContact
)
from apps.billing.billing_api.services.billing_send_service import BillingSendService
from apps.billing.billing_api.schedulers.business_hours_scheduler import BillingBusinessHoursScheduler
from apps.notifications.models import WhatsAppInstance
from apps.common.services.evolution_api_service import EvolutionAPIService

logger = logging.getLogger(__name__)


class BillingQueueConsumer:
    """
    Consumer RabbitMQ assíncrono para processamento de billing.
    
    Features:
    - Processa filas por tipo (overdue, upcoming, notification)
    - Respeita horário comercial (pausa/retoma automático)
    - Throttling configurável
    - Verifica saúde da instância antes de enviar
    - Retry automático em falhas temporárias
    - Graceful shutdown
    """
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.running = False
        self.consumer_threads = {}
        
        # Filas a serem consumidas
        self.queues = [
            'billing.overdue',
            'billing.upcoming',
            'billing.notification',
        ]
        
        logger.info("🔄 [BILLING_CONSUMER] Iniciando sistema RabbitMQ assíncrono para billing")
    
    async def _connect_async(self):
        """Estabelece conexão assíncrona com RabbitMQ"""
        max_attempts = 10
        base_delay = 1
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 [BILLING_CONSUMER] Tentativa {attempt}/{max_attempts} de conexão")
                
                if attempt > 1:
                    delay = base_delay * (2 ** (attempt - 2))
                    logger.info(f"⏳ [BILLING_CONSUMER] Aguardando {delay}s antes da tentativa {attempt}")
                    await asyncio.sleep(delay)
                
                # ✅ SECURITY: Não usar credenciais hardcoded
                rabbitmq_url = settings.RABBITMQ_URL
                safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)
                logger.info(f"🔍 [BILLING_CONSUMER] RabbitMQ URL: {safe_url}")
                
                self.connection = await aio_pika.connect_robust(
                    rabbitmq_url,
                    heartbeat=0,
                    blocked_connection_timeout=0,
                    socket_timeout=10,
                    retry_delay=1,
                    connection_attempts=1
                )
                
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)  # Processa uma mensagem por vez
                
                # Configura filas
                await self._setup_queues_async()
                
                logger.info("✅ [BILLING_CONSUMER] Conexão RabbitMQ estabelecida com sucesso!")
                return
                
            except Exception as e:
                logger.error(f"❌ [BILLING_CONSUMER] Tentativa {attempt} falhou: {e}")
                
                if attempt == max_attempts:
                    logger.error("❌ [BILLING_CONSUMER] Todas as tentativas falharam")
                    self.connection = None
                    self.channel = None
                    return
    
    async def _setup_queues_async(self):
        """Configura filas de forma assíncrona"""
        try:
            # Exchange principal
            exchange = await self.channel.declare_exchange(
                'billing',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Filas principais
            for queue_name in self.queues:
                try:
                    queue = await self.channel.declare_queue(queue_name, durable=True)
                    await queue.bind(exchange, routing_key=queue_name)
                    logger.info(f"✅ [BILLING_CONSUMER] Fila '{queue_name}' configurada")
                except Exception as e:
                    logger.error(f"❌ [BILLING_CONSUMER] Erro ao configurar fila '{queue_name}': {e}")
                    continue
            
            logger.info("✅ [BILLING_CONSUMER] Todas as filas configuradas com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [BILLING_CONSUMER] Erro geral na configuração de filas: {e}")
            raise
    
    async def start_consuming(self):
        """Inicia consumo de todas as filas"""
        try:
            if not self.connection or self.connection.is_closed:
                await self._connect_async()
            
            if not self.connection:
                logger.error("❌ [BILLING_CONSUMER] Não foi possível conectar ao RabbitMQ")
                return
            
            self.running = True
            
            # Consome cada fila em uma task separada
            tasks = []
            for queue_name in self.queues:
                task = asyncio.create_task(self._consume_queue(queue_name))
                tasks.append(task)
            
            logger.info(f"🚀 [BILLING_CONSUMER] Iniciando consumo de {len(self.queues)} filas...")
            
            # Aguarda todas as tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"❌ [BILLING_CONSUMER] Erro ao iniciar consumo: {e}", exc_info=True)
        finally:
            self.running = False
    
    async def _consume_queue(self, queue_name: str):
        """Consome mensagens de uma fila específica"""
        try:
            queue = await self.channel.declare_queue(queue_name, durable=True)
            
            logger.info(f"📥 [BILLING_CONSUMER] Consumindo fila '{queue_name}'...")
            
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.running:
                        logger.info(f"⏸️ [BILLING_CONSUMER] Parando consumo da fila '{queue_name}'")
                        break
                    
                    try:
                        # Processa mensagem
                        await self._process_message(message, queue_name)
                        
                        # Confirma processamento
                        await message.ack()
                        
                    except Exception as e:
                        logger.error(
                            f"❌ [BILLING_CONSUMER] Erro ao processar mensagem da fila '{queue_name}': {e}",
                            exc_info=True
                        )
                        # Rejeita mensagem e não reenfileira (vai para DLQ se configurado)
                        await message.nack(requeue=False)
                        
        except Exception as e:
            logger.error(
                f"❌ [BILLING_CONSUMER] Erro ao consumir fila '{queue_name}': {e}",
                exc_info=True
            )
    
    async def _process_message(self, message: aio_pika.IncomingMessage, queue_name: str):
        """
        Processa uma mensagem da fila.
        
        Args:
            message: Mensagem recebida do RabbitMQ
            queue_name: Nome da fila de origem
        """
        try:
            # Decodifica payload
            body = message.body.decode()
            payload = json.loads(body)
            
            queue_id = payload.get('queue_id')
            template_type = payload.get('template_type')
            
            if not queue_id:
                logger.error(f"❌ [BILLING_CONSUMER] Mensagem sem queue_id: {payload}")
                return
            
            logger.info(
                f"📨 [BILLING_CONSUMER] Processando queue {queue_id} "
                f"(tipo: {template_type}, fila: {queue_name})"
            )
            
            # Busca a queue no banco
            try:
                billing_queue = await self._get_queue_async(queue_id)
                if not billing_queue:
                    logger.error(f"❌ [BILLING_CONSUMER] Queue {queue_id} não encontrada")
                    return
            except Exception as e:
                logger.error(f"❌ [BILLING_CONSUMER] Erro ao buscar queue {queue_id}: {e}")
                return
            
            # Processa a queue
            await self._process_billing_queue(billing_queue, template_type)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ [BILLING_CONSUMER] Erro ao decodificar JSON: {e}")
        except Exception as e:
            logger.error(
                f"❌ [BILLING_CONSUMER] Erro ao processar mensagem: {e}",
                exc_info=True
            )
    
    async def _get_queue_async(self, queue_id: str) -> Optional[BillingQueue]:
        """Busca queue de forma assíncrona"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_queue():
            try:
                return BillingQueue.objects.select_related(
                    'billing_campaign',
                    'billing_campaign__tenant',
                    'billing_campaign__tenant__billing_config',
                    'billing_campaign__template'
                ).get(id=queue_id)
            except BillingQueue.DoesNotExist:
                return None
        
        return await get_queue()
    
    async def _process_billing_queue(self, billing_queue: BillingQueue, template_type: str):
        """
        Processa todos os contatos de uma billing queue.
        
        Args:
            billing_queue: Objeto BillingQueue
            template_type: Tipo de template
        """
        try:
            tenant = billing_queue.billing_campaign.tenant
            config = tenant.billing_config
            
            # 1. Verifica horário comercial ANTES de processar
            if not BillingBusinessHoursScheduler.is_within_business_hours(tenant):
                logger.info(
                    f"⏸️ [BILLING_CONSUMER] Fora do horário comercial para tenant {tenant.name}. "
                    f"Queue {billing_queue.id} será processada quando o horário abrir."
                )
                
                # Calcula próximo horário válido
                next_valid_dt = BillingBusinessHoursScheduler.get_next_valid_datetime(tenant)
                delay_seconds = BillingBusinessHoursScheduler.calculate_delay_until_next_hours(tenant)
                
                logger.info(
                    f"⏰ [BILLING_CONSUMER] Próximo horário válido: {next_valid_dt} "
                    f"(em {delay_seconds}s)"
                )
                
                # Atualiza status da queue para aguardar horário comercial
                await self._update_queue_status_async(billing_queue, 'paused_business_hours')
                
                # Reenfileira para processar depois (ou aguarda delay)
                if delay_seconds > 0:
                    await asyncio.sleep(min(delay_seconds, 3600))  # Máximo 1 hora de espera
                
                return
            
            # 2. Busca instância ativa
            instance = await self._get_active_instance_async(tenant)
            if not instance:
                logger.error(
                    f"❌ [BILLING_CONSUMER] Nenhuma instância ativa para tenant {tenant.name}"
                )
                await self._update_queue_status_async(billing_queue, 'paused')
                return
            
            # 3. Verifica saúde da instância
            evolution_api = EvolutionAPIService(instance)
            is_healthy, health_reason = await evolution_api.check_health()
            
            if not is_healthy:
                logger.warning(
                    f"⚠️ [BILLING_CONSUMER] Instância {instance.friendly_name} não saudável: {health_reason}. "
                    f"Queue {billing_queue.id} será processada quando a instância voltar."
                )
                await self._update_queue_status_async(billing_queue, 'paused_instance_down')
                return
            
            # 4. Atualiza status para RUNNING
            await self._update_queue_status_async(billing_queue, 'running')
            
            # 5. Busca contatos pendentes
            pending_contacts = await self._get_pending_contacts_async(billing_queue)
            
            if not pending_contacts:
                logger.info(f"✅ [BILLING_CONSUMER] Queue {billing_queue.id} não tem contatos pendentes")
                await self._update_queue_status_async(billing_queue, 'completed')
                return
            
            logger.info(
                f"📊 [BILLING_CONSUMER] Processando {len(pending_contacts)} contatos da queue {billing_queue.id}"
            )
            
            # 6. Calcula intervalo de throttling
            messages_per_minute = config.messages_per_minute or 20
            interval_seconds = max(60.0 / messages_per_minute, 3.0)  # Mínimo 3 segundos
            
            # 7. Processa cada contato
            sent_count = 0
            failed_count = 0
            
            for contact in pending_contacts:
                # Verifica horário comercial ANTES de CADA mensagem
                if not BillingBusinessHoursScheduler.is_within_business_hours(tenant):
                    logger.info(
                        f"⏸️ [BILLING_CONSUMER] Horário comercial encerrado durante processamento. "
                        f"Pausando queue {billing_queue.id}."
                    )
                    await self._update_queue_status_async(billing_queue, 'paused_business_hours')
                    break
                
                # Verifica saúde da instância ANTES de CADA mensagem
                is_healthy, health_reason = await evolution_api.check_health()
                if not is_healthy:
                    logger.warning(
                        f"⚠️ [BILLING_CONSUMER] Instância caiu durante processamento: {health_reason}. "
                        f"Pausando queue {billing_queue.id}."
                    )
                    await self._update_queue_status_async(billing_queue, 'paused_instance_down')
                    break
                
                # Processa contato
                success = await self._process_contact(contact, instance, evolution_api)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                
                # Throttling: aguarda intervalo antes do próximo envio
                await asyncio.sleep(interval_seconds)
            
            # 8. Atualiza estatísticas da queue
            await self._update_queue_stats_async(billing_queue, sent_count, failed_count)
            
            # 9. Verifica se completou ou precisa continuar
            remaining = await self._get_pending_contacts_count_async(billing_queue)
            
            if remaining == 0:
                logger.info(f"✅ [BILLING_CONSUMER] Queue {billing_queue.id} completada!")
                await self._update_queue_status_async(billing_queue, 'completed')
            else:
                logger.info(
                    f"⏳ [BILLING_CONSUMER] Queue {billing_queue.id} ainda tem {remaining} contatos pendentes. "
                    f"Será processada novamente."
                )
                await self._update_queue_status_async(billing_queue, 'pending')
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_CONSUMER] Erro ao processar queue {billing_queue.id}: {e}",
                exc_info=True
            )
            await self._update_queue_status_async(billing_queue, 'paused')
    
    async def _get_active_instance_async(self, tenant) -> Optional[WhatsAppInstance]:
        """Busca instância ativa do tenant"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_instance():
            return WhatsAppInstance.objects.filter(
                tenant=tenant,
                is_active=True,
                connection_state='open'
            ).first()
        
        return await get_instance()
    
    async def _get_pending_contacts_async(self, billing_queue: BillingQueue):
        """Busca contatos pendentes da queue"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_contacts():
            return list(
                BillingContact.objects.filter(
                    billing_campaign=billing_queue.billing_campaign,
                    campaign_contact__status__in=['pending', 'pending_retry']
                ).select_related(
                    'campaign_contact',
                    'campaign_contact__contact',
                    'template_variation',
                    'billing_campaign'
                )[:100]  # Processa até 100 por vez
            )
        
        return await get_contacts()
    
    async def _get_pending_contacts_count_async(self, billing_queue: BillingQueue) -> int:
        """Conta contatos pendentes"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def count_contacts():
            return BillingContact.objects.filter(
                billing_campaign=billing_queue.billing_campaign,
                campaign_contact__status__in=['pending', 'pending_retry']
            ).count()
        
        return await count_contacts()
    
    async def _process_contact(
        self,
        billing_contact: BillingContact,
        instance: WhatsAppInstance,
        evolution_api: EvolutionAPIService
    ) -> bool:
        """
        Processa um único contato (envia mensagem).
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            # Usa EvolutionAPIService (síncrono, executa em executor)
            from asgiref.sync import sync_to_async
            
            # Para mensagens de ciclo, pode não ter campaign_contact
            if billing_contact.campaign_contact and billing_contact.campaign_contact.contact:
                phone = billing_contact.campaign_contact.contact.phone
            elif billing_contact.billing_cycle:
                phone = billing_contact.billing_cycle.contact_phone
            else:
                logger.error(f"BillingContact {billing_contact.id} sem contato (nem campaign_contact nem billing_cycle)")
                return False
            
            message_text = billing_contact.rendered_message
            
            # Executa send_text_message em executor (é síncrono)
            loop = asyncio.get_event_loop()
            success, response = await loop.run_in_executor(
                None,
                lambda: evolution_api.send_text_message(
                    phone=phone,
                    message=message_text,
                    max_retries=3
                )
            )
            
            if success:
                # Atualiza status do BillingContact
                from asgiref.sync import sync_to_async
                
                @sync_to_async
                def update_success():
                    billing_contact.status = 'sent'
                    billing_contact.sent_at = timezone.now()
                    billing_contact.save(update_fields=['status', 'sent_at'])
                    
                    # Atualiza CampaignContact se existir (mensagens de campanha)
                    # Mensagens de ciclo não têm CampaignContact
                    campaign_contact = billing_contact.campaign_contact if billing_contact.campaign_contact else None
                    if campaign_contact:
                        campaign_contact.status = 'sent'
                        campaign_contact.sent_at = timezone.now()
                        message_id = response.get('key', {}).get('id') or response.get('id')
                        if message_id:
                            campaign_contact.whatsapp_message_id = message_id
                        campaign_contact.save(update_fields=['status', 'sent_at', 'whatsapp_message_id'])
                
                await update_success()
                
                logger.info(
                    f"✅ [BILLING_CONSUMER] Mensagem enviada para contato {phone}"
                )
            else:
                # Atualiza status de falha
                from asgiref.sync import sync_to_async
                
                @sync_to_async
                def update_failure():
                    billing_contact.status = 'failed'
                    error_msg = response.get('error', 'Erro desconhecido')
                    billing_contact.billing_data = {
                        **billing_contact.billing_data,
                        'last_error': error_msg
                    }
                    billing_contact.save(update_fields=['status', 'billing_data'])
                    
                    # Atualiza CampaignContact se existir (mensagens de campanha)
                    # Mensagens de ciclo não têm CampaignContact
                    campaign_contact = billing_contact.campaign_contact if billing_contact.campaign_contact else None
                    if campaign_contact:
                        campaign_contact.status = 'failed'
                        campaign_contact.save(update_fields=['status'])
                
                await update_failure()
                
                logger.error(
                    f"❌ [BILLING_CONSUMER] Falha ao enviar mensagem: {response.get('error', 'Erro desconhecido')}"
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_CONSUMER] Erro ao processar contato {billing_contact.id}: {e}",
                exc_info=True
            )
            return False
    
    async def _update_queue_status_async(self, billing_queue: BillingQueue, status: str):
        """Atualiza status da queue"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def update_status():
            billing_queue.status = status
            billing_queue.save(update_fields=['status'])
        
        await update_status()
    
    async def _update_queue_stats_async(self, billing_queue: BillingQueue, sent: int, failed: int):
        """Atualiza estatísticas da queue"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def update_stats():
            billing_queue.contacts_sent = (billing_queue.contacts_sent or 0) + sent
            billing_queue.contacts_failed = (billing_queue.contacts_failed or 0) + failed
            billing_queue.save(update_fields=['contacts_sent', 'contacts_failed'])
        
        await update_stats()
    
    async def close(self):
        """Fecha conexões"""
        try:
            logger.info("🔄 [BILLING_CONSUMER] Fechando conexões...")
            
            self.running = False
            
            if self.channel:
                await self.channel.close()
            if self.connection:
                await self.connection.close()
            
            logger.info("✅ [BILLING_CONSUMER] Conexões fechadas com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [BILLING_CONSUMER] Erro ao fechar conexões: {e}")


# Instância global
_consumer = None


def get_billing_consumer() -> BillingQueueConsumer:
    """Retorna a instância global do consumer"""
    global _consumer
    if _consumer is None:
        _consumer = BillingQueueConsumer()
    return _consumer


async def start_billing_consumer():
    """Função helper para iniciar o consumer em um loop de eventos"""
    consumer = get_billing_consumer()
    await consumer.start_consuming()

