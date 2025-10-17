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
        # Conexão será estabelecida quando necessário (lazy connection)
        logger.info("🔍 [DEBUG] Consumer inicializado - cada thread terá sua própria conexão")
    
    async def _connect_async(self):
        """Estabelece conexão assíncrona com RabbitMQ"""
        max_attempts = 10
        base_delay = 1
        
        logger.info("🔍 [DEBUG] Iniciando processo de conexão aio-pika")
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"🔄 [AIO-PIKA] Tentativa {attempt}/{max_attempts} de conexão")
                
                # Aguardar antes de tentar
                if attempt > 1:
                    delay = base_delay * (2 ** (attempt - 2))  # 1, 2, 4, 8, 16...
                    logger.info(f"⏳ [AIO-PIKA] Aguardando {delay}s antes da tentativa {attempt}")
                    await asyncio.sleep(delay)
                
                # Tentar conexão com aio-pika
                rabbitmq_url = getattr(settings, 'RABBITMQ_URL', 'amqp://75jkOmkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672')
                logger.info(f"🔍 [DEBUG] RabbitMQ URL: {rabbitmq_url[:50]}...")
                
                logger.info("🔍 [DEBUG] Chamando aio_pika.connect_robust...")
                self.connection = await aio_pika.connect_robust(
                    rabbitmq_url,
                    heartbeat=0,  # Desabilitar heartbeat
                    blocked_connection_timeout=0,
                    socket_timeout=10,
                    retry_delay=1,
                    connection_attempts=1
                )
                logger.info("🔍 [DEBUG] Conexão aio_pika.connect_robust estabelecida")
                
                logger.info("🔍 [DEBUG] Criando channel...")
                self.channel = await self.connection.channel()
                logger.info("🔍 [DEBUG] Channel criado")
                
                logger.info("🔍 [DEBUG] Configurando QoS...")
                await self.channel.set_qos(prefetch_count=1)
                logger.info("🔍 [DEBUG] QoS configurado")
                
                # Configurar filas
                logger.info("🔍 [DEBUG] Configurando filas...")
                await self._setup_queues_async()
                logger.info("🔍 [DEBUG] Filas configuradas")
                
                logger.info("✅ [AIO-PIKA] Conexão RabbitMQ estabelecida com sucesso!")
                logger.info(f"🔍 [DEBUG] Connection state: {self.connection.is_closed}")
                logger.info(f"🔍 [DEBUG] Channel state: {self.channel.is_closed}")
                return
                
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Tentativa {attempt} falhou: {e}")
                logger.error(f"🔍 [DEBUG] Tipo do erro: {type(e).__name__}")
                logger.error(f"🔍 [DEBUG] Detalhes do erro: {str(e)}")
                
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
    
    async def _check_connection(self, thread_connection=None):
        """Verifica se a conexão está ativa"""
        try:
            # Usar conexão da thread se fornecida, senão usar conexão global
            connection = thread_connection if thread_connection else self.connection
            
            logger.info("🔍 [DEBUG] Verificando conexão...")
            logger.info(f"🔍 [DEBUG] Connection exists: {connection is not None}")
            
            if connection:
                logger.info(f"🔍 [DEBUG] Connection is_closed: {connection.is_closed}")
                
            if not connection or connection.is_closed:
                logger.warning("⚠️ [AIO-PIKA] Conexão perdida, reconectando...")
                # Se for thread connection, não reconectar aqui
                if thread_connection:
                    return False
                await self._connect_async()
                return False
            
            logger.info("🔍 [DEBUG] Conexão está ativa")
            return True
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao verificar conexão: {e}")
            logger.error(f"🔍 [DEBUG] Tipo do erro na verificação: {type(e).__name__}")
            if not thread_connection:
                await self._connect_async()
            return False
    
    def start_campaign(self, campaign_id: str):
        """Inicia o processamento de uma campanha"""
        try:
            logger.info(f"🚀 [AIO-PIKA] Iniciando campanha {campaign_id}")
            logger.info(f"🔍 [DEBUG] Threads ativas: {list(self.consumer_threads.keys())}")
            
            # Verificar se já está rodando
            if campaign_id in self.consumer_threads:
                thread = self.consumer_threads[campaign_id]
                if thread.is_alive():
                    logger.warning(f"⚠️ [AIO-PIKA] Campanha {campaign_id} já está rodando")
                    return False
                else:
                    logger.info(f"🔍 [DEBUG] Thread da campanha {campaign_id} está morta, removendo...")
                    del self.consumer_threads[campaign_id]
            
            logger.info(f"🔍 [DEBUG] Criando thread para campanha {campaign_id}")
            # Criar thread para processar a campanha
            thread = threading.Thread(
                target=self._run_campaign_async,
                args=(campaign_id,),
                daemon=True
            )
            
            logger.info(f"🔍 [DEBUG] Iniciando thread para campanha {campaign_id}")
            thread.start()
            
            self.consumer_threads[campaign_id] = thread
            logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} iniciada com sucesso")
            logger.info(f"🔍 [DEBUG] Threads ativas após start: {list(self.consumer_threads.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao iniciar campanha {campaign_id}: {e}")
            logger.error(f"🔍 [DEBUG] Tipo do erro no start_campaign: {type(e).__name__}")
            return False
    
    def _run_campaign_async(self, campaign_id: str):
        """Executa campanha em loop assíncrono"""
        try:
            logger.info(f"🔍 [DEBUG] Iniciando _run_campaign_async para {campaign_id}")
            
            # Criar novo event loop para a thread
            logger.info(f"🔍 [DEBUG] Criando novo event loop para {campaign_id}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            logger.info(f"🔍 [DEBUG] Event loop criado, executando campanha {campaign_id}")
            # Executar campanha
            loop.run_until_complete(self._process_campaign_async(campaign_id))
            
            logger.info(f"🔍 [DEBUG] Campanha {campaign_id} finalizada normalmente")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro no processamento da campanha {campaign_id}: {e}")
            logger.error(f"🔍 [DEBUG] Tipo do erro no _run_campaign_async: {type(e).__name__}")
        finally:
            # Limpar thread
            logger.info(f"🔍 [DEBUG] Limpando thread da campanha {campaign_id}")
            if campaign_id in self.consumer_threads:
                del self.consumer_threads[campaign_id]
                logger.info(f"🔍 [DEBUG] Thread da campanha {campaign_id} removida")
    
    async def _process_campaign_async(self, campaign_id: str):
        """Processa campanha de forma assíncrona"""
        thread_connection = None
        thread_channel = None
        
        try:
            logger.info(f"🔄 [AIO-PIKA] Iniciando processamento da campanha {campaign_id}")
            
            # Criar conexão própria para esta thread
            logger.info(f"🔍 [DEBUG] Criando conexão própria para campanha {campaign_id}")
            thread_connection = await self._create_thread_connection()
            if not thread_connection:
                logger.error(f"❌ [AIO-PIKA] Falha ao criar conexão para campanha {campaign_id}")
                return
            
            thread_channel = await thread_connection.channel()
            await thread_channel.set_qos(prefetch_count=1)
            logger.info(f"✅ [AIO-PIKA] Conexão criada para campanha {campaign_id}")
            
            loop_count = 0
            
            while True:
                try:
                    loop_count += 1
                    logger.info(f"🔍 [DEBUG] Loop {loop_count} da campanha {campaign_id}")
                    
                    # Verificar conexão da thread
                    logger.info(f"🔍 [DEBUG] Verificando conexão para campanha {campaign_id}")
                    if not await self._check_connection(thread_connection):
                        logger.warning("⚠️ [AIO-PIKA] Conexão da thread perdida, recriando...")
                        # Recriar conexão da thread
                        thread_connection = await self._create_thread_connection()
                        if thread_connection:
                            thread_channel = await thread_connection.channel()
                            await thread_channel.set_qos(prefetch_count=1)
                            logger.info(f"✅ [AIO-PIKA] Conexão da thread recriada para campanha {campaign_id}")
                        else:
                            await asyncio.sleep(5)
                            continue
                    
                    # Buscar campanha
                    logger.info(f"🔍 [DEBUG] Buscando campanha {campaign_id} no banco")
                    campaign = await self._get_campaign_async(campaign_id)
                    if not campaign:
                        logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                        break
                    
                    logger.info(f"🔍 [DEBUG] Campanha encontrada: {campaign.name} - Status: {campaign.status}")
                    
                    # Verificar status
                    if campaign.status not in ['active', 'running']:
                        logger.info(f"⏸️ [AIO-PIKA] Campanha {campaign_id} pausada/parada (status: {campaign.status})")
                        break
                    
                    # Processar próxima mensagem
                    logger.info(f"🔍 [DEBUG] Processando próxima mensagem da campanha {campaign_id}")
                    logger.info(f"🔍 [DEBUG] Campanha status: {campaign.status}, total_contacts: {campaign.total_contacts}")
                    await self._process_next_message_async(campaign)
                    
                    # 🎯 HUMANIZAÇÃO: Aguardar intervalo aleatório entre min e max configurados
                    # Adicionar +20% ao intervalo máximo para parecer mais humano
                    import random
                    min_interval = campaign.interval_min
                    max_interval = int(campaign.interval_max * 1.2)  # 20% a mais
                    random_interval = random.uniform(min_interval, max_interval)
                    
                    logger.info(f"⏰ [INTERVAL] Aguardando {random_interval:.1f}s antes do próximo disparo (min={min_interval}s, max={max_interval}s)")
                    await asyncio.sleep(random_interval)
                    
                except Exception as e:
                    logger.error(f"❌ [AIO-PIKA] Erro no loop da campanha {campaign_id}: {e}")
                    logger.error(f"🔍 [DEBUG] Tipo do erro no loop: {type(e).__name__}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro crítico no processamento da campanha {campaign_id}: {e}")
            logger.error(f"🔍 [DEBUG] Tipo do erro crítico: {type(e).__name__}")
        finally:
            # Fechar conexão da thread
            if thread_channel:
                try:
                    await thread_channel.close()
                except:
                    pass
            if thread_connection:
                try:
                    await thread_connection.close()
                except:
                    pass
            logger.info(f"🔍 [DEBUG] Conexão da thread fechada para campanha {campaign_id}")
    
    async def _create_thread_connection(self):
        """Cria uma conexão específica para uma thread"""
        try:
            # Verificar se estamos em desenvolvimento local (localhost)
            import socket
            hostname = socket.gethostname()
            # Permitir RabbitMQ em desenvolvimento local para testes
            # if settings.DEBUG and ('localhost' in hostname or '127.0.0.1' in hostname):
            #     logger.info("🔍 [DEBUG] Ambiente local - RabbitMQ desabilitado")
            #     return None
            
            rabbitmq_url = getattr(settings, 'RABBITMQ_URL', 'amqp://75jkOmkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672')
            
            logger.info("🔍 [DEBUG] Criando conexão da thread...")
            connection = await aio_pika.connect_robust(
                rabbitmq_url,
                heartbeat=0,
                blocked_connection_timeout=0,
                socket_timeout=10,
                retry_delay=1,
                connection_attempts=1
            )
            
            logger.info("✅ [AIO-PIKA] Conexão da thread criada com sucesso")
            return connection
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar conexão da thread: {e}")
            return None
    
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
                from .models import CampaignContact
                return CampaignContact.objects.filter(
                    campaign=campaign,
                    status='pending'
                ).order_by('created_at').first()
            
            contact = await get_next_contact()

            if not contact:
                logger.info(f"✅ [AIO-PIKA] Campanha {campaign.id} - Todos os contatos processados")
                logger.info(f"🔍 [DEBUG] Campanha {campaign.id} - Status atual: {campaign.status}")
                # Atualizar status da campanha
                await self._update_campaign_status_async(campaign, 'completed')
                return
            
            logger.info(f"🔍 [DEBUG] Próximo contato encontrado: {contact.id} - Status: {contact.status}")
            
            # Marcar contato como enviando
            await self._update_contact_status_async(contact, 'sending')

            # Enviar mensagem
            await self._send_message_async(campaign, contact)
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao processar próxima mensagem: {e}")
    
    async def _update_contact_status_async(self, contact, status):
        """Atualiza o status do contato de forma assíncrona"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def update_status():
                contact.status = status
                contact.save()
            
            await update_status()
            logger.info(f"✅ [AIO-PIKA] Status do contato {contact.id} atualizado para {status}")
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao atualizar status do contato {contact.id}: {e}")

    async def _update_campaign_status_async(self, campaign, status):
        """Atualiza o status da campanha de forma assíncrona"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def update_status():
                campaign.status = status
                campaign.save()
            
            await update_status()
            logger.info(f"✅ [AIO-PIKA] Status da campanha {campaign.id} atualizado para {status}")
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao atualizar status da campanha {campaign.id}: {e}")
    
    async def _send_message_async(self, campaign, contact):
        """Envia mensagem de forma assíncrona"""
        try:
            from asgiref.sync import sync_to_async
            
            # Buscar telefone de forma assíncrona
            @sync_to_async
            def get_contact_phone():
                return contact.contact.phone
            
            contact_phone = await get_contact_phone()
            logger.info(f"📤 [AIO-PIKA] Enviando mensagem para {contact_phone} - Campanha {campaign.id}")
            
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
                await self._update_campaign_status_async(campaign, 'paused')
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
                logger.error(f"❌ [AIO-PIKA] Falha ao enviar mensagem para {contact_phone}")
                # Marcar como falha
                @sync_to_async
                def mark_failed():
                    contact.status = 'failed'
                    contact.save()
                
                await mark_failed()
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao enviar mensagem: {e}")
            logger.error(f"🔍 [DEBUG] Tipo do erro: {type(e).__name__}")
            logger.error(f"🔍 [DEBUG] Detalhes do erro: {str(e)}")
            import traceback
            logger.error(f"🔍 [DEBUG] Stack trace: {traceback.format_exc()}")
    
    async def _send_typing_presence(self, instance, contact_phone, typing_seconds):
        """Envia status 'digitando' antes da mensagem para parecer mais humano"""
        try:
            presence_url = f"{instance.api_url}/chat/sendPresence/{instance.instance_name}"
            presence_data = {
                "number": contact_phone,
                "options": {
                    "delay": int(typing_seconds * 1000),  # Converter para milissegundos
                    "presence": "composing"
                }
            }
            headers = {
                "Content-Type": "application/json",
                "apikey": instance.api_key
            }
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: requests.post(presence_url, json=presence_data, headers=headers, timeout=10)
            )
            
            logger.info(f"✍️ [PRESENCE] Enviando status 'digitando' para {contact_phone} por {typing_seconds}s")
            
            # Aguardar o tempo de digitação
            await asyncio.sleep(typing_seconds)
            
        except Exception as e:
            logger.warning(f"⚠️ [PRESENCE] Erro ao enviar status 'digitando': {e}")
            # Não falhar o envio se o presence falhar

    async def _send_whatsapp_message_async(self, campaign, contact, instance):
        """Envia mensagem WhatsApp com retry e controle de erros"""
        from asgiref.sync import sync_to_async
        import random
        
        max_retries = 3
        base_delay = 2
        
        # Buscar telefone de forma assíncrona
        @sync_to_async
        def get_contact_phone():
            return contact.contact.phone
        
        contact_phone = await get_contact_phone()
        logger.info(f"🔍 [DEBUG] Iniciando envio de mensagem para {contact_phone}")
        logger.info(f"🔍 [DEBUG] Campanha: {campaign.name} - Instância: {instance.instance_name}")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔍 [DEBUG] Tentativa {attempt}/{max_retries} de envio")
                
                # Verificar se instância ainda está ativa
                logger.info(f"🔍 [DEBUG] Verificando se instância {instance.instance_name} está ativa")
                if not await self._check_instance_active(instance):
                    logger.error(f"❌ [AIO-PIKA] Instância {instance.instance_name} inativa - pausando campanha")
                    await self._auto_pause_campaign(campaign, "instância desconectada")
                    return False
                
                logger.info(f"🔍 [DEBUG] Instância {instance.instance_name} está ativa")
                
                # Buscar mensagem da campanha
                from asgiref.sync import sync_to_async
                
                @sync_to_async
                def get_message():
                    return campaign.messages.first()
                
                message = await get_message()
                
                if not message:
                    logger.error(f"❌ [AIO-PIKA] Nenhuma mensagem encontrada para campanha {campaign.id}")
                    return False
                
                # 🎯 HUMANIZAÇÃO: Enviar status "digitando" com tempo aleatório entre 1.5s e 4s
                typing_seconds = random.uniform(1.5, 4.0)
                await self._send_typing_presence(instance, contact_phone, typing_seconds)
                
                # Preparar dados da mensagem
                message_data = {
                    "number": contact_phone,
                    "text": message.content,
                    "instance": instance.instance_name
                }
                
                # Enviar via Evolution API
                url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
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
                
                # ✅ Aceitar status 200 (OK) e 201 (Created) como sucesso
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    # Evolution API pode retornar 'sent' ou 'key' (ambos indicam sucesso)
                    if response_data.get('sent') or response_data.get('key'):
                        logger.info(f"✅ [AIO-PIKA] Mensagem enviada com sucesso para {contact_phone} (tentativa {attempt})")
                        
                        # Salvar message_id (pode estar em 'messageId' ou 'key.id')
                        message_id = response_data.get('messageId')
                        if not message_id and response_data.get('key'):
                            message_id = response_data['key'].get('id')
                        
                        if message_id:
                            @sync_to_async
                            def save_message_id():
                                contact.whatsapp_message_id = message_id
                                contact.save()
                            
                            await save_message_id()
                        
                        # Log de sucesso
                        await self._log_message_sent(campaign, contact, instance, message_id, contact_phone)
                        
                        return True
                    else:
                        error_msg = response_data.get('message', 'Erro desconhecido')
                        logger.error(f"❌ [AIO-PIKA] API retornou erro (tentativa {attempt}): {error_msg}")
                        
                        # Verificar se é erro de instância inativa
                        if 'instance' in error_msg.lower() or 'disconnected' in error_msg.lower():
                            await self._auto_pause_campaign(campaign, f"instância desconectada: {error_msg}")
                            return False
                        
                        # Tentar novamente se não for erro de instância
                        if attempt < max_retries:
                            delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s
                            logger.info(f"⏳ [AIO-PIKA] Tentando novamente em {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # Log de falha final
                            await self._log_message_failed(campaign, contact, instance, error_msg, contact_phone)
                            return False
                else:
                    logger.error(f"❌ [AIO-PIKA] Erro HTTP {response.status_code} (tentativa {attempt}): {response.text}")
                    
                    # Verificar se é erro de instância inativa (500 pode indicar instância offline)
                    if response.status_code == 500:
                        await self._auto_pause_campaign(campaign, "instância retornou erro 500")
                        return False
                    
                    # Tentar novamente se não for erro crítico
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s
                        logger.info(f"⏳ [AIO-PIKA] Tentando novamente em {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Log de falha final
                        await self._log_message_failed(campaign, contact, instance, f"HTTP {response.status_code}", contact_phone)
                        return False

            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Erro ao enviar mensagem WhatsApp (tentativa {attempt}): {e}")
                logger.error(f"🔍 [DEBUG] Tipo do erro no WhatsApp: {type(e).__name__}")
                logger.error(f"🔍 [DEBUG] Detalhes do erro no WhatsApp: {str(e)}")
                import traceback
                logger.error(f"🔍 [DEBUG] Stack trace WhatsApp: {traceback.format_exc()}")

                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s
                    logger.info(f"⏳ [AIO-PIKA] Tentando novamente em {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Log de falha final
                    await self._log_message_failed(campaign, contact, instance, str(e), contact_phone)
                    return False
        
        return False
    
    async def _check_instance_active(self, instance):
        """Verifica se a instância está ativa"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def check_instance():
                # Buscar instância atualizada do banco
                try:
                    current_instance = WhatsAppInstance.objects.get(id=instance.id)
                    return current_instance.is_active
                except WhatsAppInstance.DoesNotExist:
                    return False
            
            return await check_instance()
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao verificar instância: {e}")
            return False
    
    async def _auto_pause_campaign(self, campaign, reason):
        """Pausa campanha automaticamente"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def pause_campaign():
                campaign.status = 'paused'
                campaign.save()
                
                # Log da pausa automática
                CampaignLog.objects.create(
                    campaign=campaign,
                    event_type='campaign_auto_paused',
                    message=f'Campanha pausada automaticamente: {reason}',
                    extra_data={'reason': reason}
                )
            
            await pause_campaign()
            logger.warning(f"⚠️ [AIO-PIKA] Campanha {campaign.id} pausada automaticamente: {reason}")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao pausar campanha automaticamente: {e}")
    
    async def _log_message_sent(self, campaign, contact, instance, message_id, contact_phone):
        """Log de mensagem enviada"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def create_log():
                CampaignLog.objects.create(
                    campaign=campaign,
                    event_type='message_sent',
                    message=f'Mensagem enviada para {contact_phone}',
                    extra_data={
                        'contact_id': str(contact.id),
                        'phone': contact_phone,
                        'instance_id': instance.instance_name,
                        'message_id': message_id
                    }
                )
            
            await create_log()
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar log de mensagem enviada: {e}")
    
    async def _log_message_failed(self, campaign, contact, instance, error_msg, contact_phone):
        """Log de mensagem falhada"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def create_log():
                CampaignLog.objects.create(
                    campaign=campaign,
                    event_type='message_failed',
                    message=f'Falha ao enviar mensagem para {contact_phone}: {error_msg}',
                    extra_data={
                        'contact_id': str(contact.id),
                        'phone': contact_phone,
                        'instance_id': instance.instance_name,
                        'error': error_msg
                    }
                )
            
            await create_log()
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar log de mensagem falhada: {e}")
    
    def pause_campaign(self, campaign_id: str):
        """Pausa uma campanha"""
        try:
            logger.info(f"⏸️ [AIO-PIKA] Pausando campanha {campaign_id}")
            
            # Parar thread se estiver rodando
            if campaign_id in self.consumer_threads:
                # A thread vai parar naturalmente no próximo loop
                logger.info(f"🔄 [AIO-PIKA] Thread da campanha {campaign_id} será finalizada")
            
            # Atualizar status no banco de forma síncrona
            try:
                from asgiref.sync import sync_to_async
                import asyncio
                
                @sync_to_async
                def update_campaign_status():
                    try:
                        campaign = Campaign.objects.get(id=campaign_id)
                        campaign.status = 'paused'
                        campaign.save()
                        return True
                    except Campaign.DoesNotExist:
                        return False
                
                # Executar de forma síncrona
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(update_campaign_status())
                loop.close()
                
                if success:
                    logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} pausada com sucesso")
                    return True
                else:
                    logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                    return False
                
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Erro ao pausar campanha {campaign_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao pausar campanha {campaign_id}: {e}")
            return False
    
    def resume_campaign(self, campaign_id: str):
        """Retoma uma campanha pausada"""
        try:
            logger.info(f"▶️ [AIO-PIKA] Retomando campanha {campaign_id}")
            
            # Atualizar status no banco de forma síncrona
            try:
                from asgiref.sync import sync_to_async
                import asyncio
                
                @sync_to_async
                def update_campaign_status():
                    try:
                        campaign = Campaign.objects.get(id=campaign_id)
                        campaign.status = 'active'
                        campaign.save()
                        return True
                    except Campaign.DoesNotExist:
                        return False
                
                # Executar de forma síncrona
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(update_campaign_status())
                loop.close()
                
                if success:
                    # Iniciar processamento
                    return self.start_campaign(campaign_id)
                else:
                    logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                    return False
                
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Erro ao retomar campanha {campaign_id}: {e}")
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
            
            # Atualizar status no banco de forma síncrona
            try:
                from asgiref.sync import sync_to_async
                import asyncio
                
                @sync_to_async
                def update_campaign_status():
                    try:
                        campaign = Campaign.objects.get(id=campaign_id)
                        campaign.status = 'stopped'
                        campaign.save()
                        return True
                    except Campaign.DoesNotExist:
                        return False
                
                # Executar de forma síncrona
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(update_campaign_status())
                loop.close()
                
                if success:
                    logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} parada com sucesso")
                    return True
                else:
                    logger.error(f"❌ [AIO-PIKA] Campanha {campaign_id} não encontrada")
                    return False
                
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Erro ao parar campanha {campaign_id}: {e}")
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


def get_rabbitmq_consumer():
    """Retorna a instância global do consumer"""
    return consumer