"""
Consumer RabbitMQ com aio-pika - Sistema de Campanhas
Implementa processamento assíncrono robusto
"""
import asyncio
import json
import time
import random
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import aio_pika
import requests

from .models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """Consumer RabbitMQ assíncrono para processamento de campanhas"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.running = False
        self.consumer_threads = {}
        # Controle de throttling para WebSocket
        self.last_websocket_update = {}  # {campaign_id: timestamp}
        self.websocket_throttle_seconds = 1  # Mínimo 1 segundo entre updates
        
        # Usar aio-pika para conexão assíncrona robusta
        logger.info("🔄 [AIO-PIKA] Iniciando sistema RabbitMQ assíncrono")
        asyncio.create_task(self._connect_async())
    
    async def _connect_async(self):
        """Estabelece conexão assíncrona com RabbitMQ"""
        max_attempts = 10
        base_delay = 1
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 [AIO-PIKA] Tentativa {attempt}/{max_attempts} de conexão")
                
                # Aguardar antes de tentar
                if attempt > 1:
                    delay = base_delay * (2 ** (attempt - 2))  # 1, 2, 4, 8, 16...
                    logger.info(f"⏳ [AIO-PIKA] Aguardando {delay}s antes da tentativa {attempt}")
                    await asyncio.sleep(delay)
                
                # Tentar conexão com aio-pika
                rabbitmq_url = getattr(settings, 'RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
                
                self.connection = await aio_pika.connect_robust(
                    rabbitmq_url,
                    heartbeat=0,  # Desabilitar heartbeat
                    blocked_connection_timeout=0,
                    socket_timeout=10,
                    retry_delay=1,
                    connection_attempts=1
                )
                
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)
                
                # Configurar filas
                await self._setup_queues_async()
                
                logger.info("✅ [AIO-PIKA] Conexão RabbitMQ estabelecida com sucesso!")
                return
                
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Tentativa {attempt} falhou: {e}")
                
                if attempt == max_attempts:
                    logger.error("❌ [AIO-PIKA] Todas as tentativas falharam")
                    self.connection = None
                    self.channel = None
                    return
    
    async def _setup_queues_async(self):
        """Configura filas de forma assíncrona"""
        try:
            # Exchange principal
            await self.channel.declare_exchange(
                name='campaigns',
                type=aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Filas principais
            queues = [
                'campaign.control',      # Comandos de controle
                'campaign.messages',     # Mensagens para envio
                'campaign.retry',        # Retry de mensagens
                'campaign.dlq',          # Dead letter queue
                'campaign.health'        # Health checks
            ]
            
            for queue_name in queues:
                try:
                    queue = await self.channel.declare_queue(
                        name=queue_name,
                        durable=True
                    )
                    await queue.bind(
                        exchange='campaigns',
                        routing_key=queue_name
                    )
                    logger.info(f"✅ [AIO-PIKA] Fila '{queue_name}' configurada")
                except Exception as e:
                    logger.error(f"❌ [AIO-PIKA] Erro ao configurar fila '{queue_name}': {e}")
                    continue
            
            logger.info("✅ [AIO-PIKA] Todas as filas configuradas com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro geral na configuração de filas: {e}")
            raise
    
    async def _check_connection(self):
        """Verifica se a conexão está ativa"""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("⚠️ [AIO-PIKA] Conexão perdida, reconectando...")
                await self._connect_async()
                return False
            return True
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao verificar conexão: {e}")
            await self._connect_async()
            return False
    
    def start_campaign(self, campaign_id: str):
        """Inicia o processamento de uma campanha"""
        try:
            logger.info(f"🚀 [AIO-PIKA] Iniciando campanha {campaign_id}")
            
            # Verificar se já está rodando
            if campaign_id in self.consumer_threads:
                logger.warning(f"⚠️ [AIO-PIKA] Campanha {campaign_id} já está rodando")
                return False
            
            # Criar thread para processar a campanha
            thread = threading.Thread(
                target=self._run_campaign_async,
                args=(campaign_id,),
                daemon=True
            )
            thread.start()
            
            self.consumer_threads[campaign_id] = thread
            logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} iniciada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao iniciar campanha {campaign_id}: {e}")
            return False
    
    def _run_campaign_async(self, campaign_id: str):
        """Executa campanha em loop assíncrono"""
        try:
            # Criar novo event loop para a thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Executar campanha
            loop.run_until_complete(self._process_campaign_async(campaign_id))
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro no processamento da campanha {campaign_id}: {e}")
        finally:
            # Limpar thread
            if campaign_id in self.consumer_threads:
                del self.consumer_threads[campaign_id]
    
    async def _process_campaign_async(self, campaign_id: str):
        """Processa campanha de forma assíncrona"""
        try:
            logger.info(f"🔄 [AIO-PIKA] Iniciando processamento da campanha {campaign_id}")
            
            while True:
                try:
                    # Verificar conexão
                    if not await self._check_connection():
                        logger.warning("⚠️ [AIO-PIKA] Aguardando reconexão...")
                        await asyncio.sleep(5)
                        continue
                    
                    # Buscar campanha
                    campaign = await self._get_campaign_async(campaign_id)
                    if not campaign:
                        logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                        break
                    
                    # Verificar status
                    if campaign.status not in ['active', 'running']:
                        logger.info(f"⏸️ [AIO-PIKA] Campanha {campaign_id} pausada/parada")
                        break
                    
                    # Processar próxima mensagem
                    await self._process_next_message_async(campaign)
                    
                    # Aguardar antes da próxima iteração
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ [AIO-PIKA] Erro no loop da campanha {campaign_id}: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro crítico no processamento da campanha {campaign_id}: {e}")
    
    async def _get_campaign_async(self, campaign_id: str):
        """Busca campanha de forma assíncrona"""
        try:
            # Usar sync_to_async para operações Django
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def get_campaign():
                try:
                    return Campaign.objects.get(id=campaign_id)
                except Campaign.DoesNotExist:
                    return None
            
            return await get_campaign()
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao buscar campanha {campaign_id}: {e}")
            return None
    
    async def _process_next_message_async(self, campaign):
        """Processa próxima mensagem da campanha"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def get_next_contact():
                return campaign.contacts.filter(
                    status='pending'
                ).order_by('created_at').first()
            
            contact = await get_next_contact()
            
            if not contact:
                logger.info(f"✅ [AIO-PIKA] Campanha {campaign.id} - Todos os contatos processados")
                # Pausar campanha
                campaign.status = 'completed'
                campaign.save()
                return
            
            # Processar mensagem
            await self._send_message_async(campaign, contact)
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao processar próxima mensagem: {e}")
    
    async def _send_message_async(self, campaign, contact):
        """Envia mensagem de forma assíncrona"""
        try:
            from asgiref.sync import sync_to_async
            
            logger.info(f"📤 [AIO-PIKA] Enviando mensagem para {contact.phone} - Campanha {campaign.id}")
            
            # Buscar instância ativa
            @sync_to_async
            def get_active_instance():
                return WhatsAppInstance.objects.filter(
                    tenant=campaign.tenant,
                    is_active=True
                ).first()
            
            instance = await get_active_instance()
            
            if not instance:
                logger.error(f"❌ [AIO-PIKA] Nenhuma instância ativa para campanha {campaign.id}")
                # Pausar campanha
                campaign.status = 'paused'
                campaign.save()
                return
            
            # Enviar mensagem
            success = await self._send_whatsapp_message_async(campaign, contact, instance)
            
            if success:
                # Marcar como enviado
                @sync_to_async
                def mark_sent():
                    contact.status = 'sent'
                    contact.sent_at = timezone.now()
                    contact.save()
                
                await mark_sent()
                
                # Aguardar delay da campanha
                delay_seconds = campaign.delay_between_messages or 30
                logger.info(f"⏳ [AIO-PIKA] Aguardando {delay_seconds}s antes da próxima mensagem")
                await asyncio.sleep(delay_seconds)
                
            else:
                logger.error(f"❌ [AIO-PIKA] Falha ao enviar mensagem para {contact.phone}")
                # Marcar como falha
                @sync_to_async
                def mark_failed():
                    contact.status = 'failed'
                    contact.save()
                
                await mark_failed()
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao enviar mensagem: {e}")
    
    async def _send_whatsapp_message_async(self, campaign, contact, instance):
        """Envia mensagem WhatsApp de forma assíncrona"""
        try:
            # Buscar mensagem da campanha
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def get_message():
                return campaign.messages.first()
            
            message = await get_message()
            
            if not message:
                logger.error(f"❌ [AIO-PIKA] Nenhuma mensagem encontrada para campanha {campaign.id}")
                return False
            
            # Preparar dados da mensagem
            message_data = {
                "number": contact.phone,
                "text": message.content,
                "instance": instance.instance_id
            }
            
            # Enviar via Evolution API
            url = f"{instance.server_url}/message/sendText/{instance.instance_id}"
            headers = {
                "Content-Type": "application/json",
                "apikey": instance.api_key
            }
            
            # Usar requests de forma assíncrona
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=message_data, headers=headers, timeout=30)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('sent'):
                    logger.info(f"✅ [AIO-PIKA] Mensagem enviada com sucesso para {contact.phone}")
                    
                    # Salvar message_id
                    message_id = response_data.get('messageId')
                    if message_id:
                        @sync_to_async
                        def save_message_id():
                            contact.whatsapp_message_id = message_id
                            contact.save()
                        
                        await save_message_id()
                    
                    return True
                else:
                    logger.error(f"❌ [AIO-PIKA] API retornou erro: {response_data}")
                    return False
            else:
                logger.error(f"❌ [AIO-PIKA] Erro HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao enviar mensagem WhatsApp: {e}")
            return False
    
    def pause_campaign(self, campaign_id: str):
        """Pausa uma campanha"""
        try:
            logger.info(f"⏸️ [AIO-PIKA] Pausando campanha {campaign_id}")
            
            # Parar thread se estiver rodando
            if campaign_id in self.consumer_threads:
                # A thread vai parar naturalmente no próximo loop
                logger.info(f"🔄 [AIO-PIKA] Thread da campanha {campaign_id} será finalizada")
            
            # Atualizar status no banco
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = 'paused'
                campaign.save()
                logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} pausada com sucesso")
                return True
            except Campaign.DoesNotExist:
                logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                return False
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao pausar campanha {campaign_id}: {e}")
            return False
    
    def resume_campaign(self, campaign_id: str):
        """Retoma uma campanha pausada"""
        try:
            logger.info(f"▶️ [AIO-PIKA] Retomando campanha {campaign_id}")
            
            # Atualizar status no banco
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = 'active'
                campaign.save()
                
                # Iniciar processamento
                return self.start_campaign(campaign_id)
                
            except Campaign.DoesNotExist:
                logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                return False
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao retomar campanha {campaign_id}: {e}")
            return False
    
    def stop_campaign(self, campaign_id: str):
        """Para uma campanha definitivamente"""
        try:
            logger.info(f"⏹️ [AIO-PIKA] Parando campanha {campaign_id}")
            
            # Parar thread se estiver rodando
            if campaign_id in self.consumer_threads:
                # A thread vai parar naturalmente no próximo loop
                logger.info(f"🔄 [AIO-PIKA] Thread da campanha {campaign_id} será finalizada")
            
            # Atualizar status no banco
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = 'stopped'
                campaign.save()
                logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} parada com sucesso")
                return True
            except Campaign.DoesNotExist:
                logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                return False
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao parar campanha {campaign_id}: {e}")
            return False
    
    def get_campaign_status(self, campaign_id: str):
        """Retorna status de uma campanha"""
        try:
            if campaign_id in self.consumer_threads:
                thread = self.consumer_threads[campaign_id]
                if thread.is_alive():
                    return "running"
                else:
                    # Thread morta, remover
                    del self.consumer_threads[campaign_id]
                    return "stopped"
            else:
                return "stopped"
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao verificar status da campanha {campaign_id}: {e}")
            return "error"
    
    def get_all_campaigns_status(self):
        """Retorna status de todas as campanhas"""
        try:
            status = {}
            for campaign_id in list(self.consumer_threads.keys()):
                status[campaign_id] = self.get_campaign_status(campaign_id)
            return status
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao verificar status das campanhas: {e}")
            return {}
    
    async def close(self):
        """Fecha conexões"""
        try:
            logger.info("🔄 [AIO-PIKA] Fechando conexões...")
            
            # Parar todas as threads
            for campaign_id in list(self.consumer_threads.keys()):
                self.stop_campaign(campaign_id)
            
            # Fechar conexão
            if self.channel:
                await self.channel.close()
            if self.connection:
                await self.connection.close()
            
            logger.info("✅ [AIO-PIKA] Conexões fechadas com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao fechar conexões: {e}")


# Instância global
consumer = RabbitMQConsumer()