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
                # ✅ SECURITY FIX: Não usar credenciais hardcoded
                rabbitmq_url = settings.RABBITMQ_URL
                # Log seguro (mascarar credenciais)
                import re
                safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)
                logger.info(f"🔍 [DEBUG] RabbitMQ URL: {safe_url}")
                
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
            
            # ✅ CORREÇÃO: Inicializar next_message_scheduled_at ao iniciar campanha
            # para que o countdown apareça desde o início
            from .models import Campaign
            from django.utils import timezone
            from datetime import timedelta
            import random
            
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                if campaign.status == 'running' and not campaign.next_message_scheduled_at:
                    # Calcular primeiro disparo baseado no intervalo
                    min_interval = campaign.interval_min
                    max_interval = campaign.interval_max
                    random_interval = random.uniform(min_interval, max_interval)
                    campaign.next_message_scheduled_at = timezone.now() + timedelta(seconds=random_interval)
                    campaign.save(update_fields=['next_message_scheduled_at'])
                    logger.info(f"⏰ [AIO-PIKA] Primeiro disparo agendado para: {campaign.next_message_scheduled_at} (em {random_interval:.1f}s)")
            except Campaign.DoesNotExist:
                logger.warning(f"⚠️ [AIO-PIKA] Campanha {campaign_id} não encontrada ao inicializar scheduled_time")
            except Exception as e:
                logger.error(f"❌ [AIO-PIKA] Erro ao inicializar scheduled_time: {e}")
            
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
                    
                    # ✅ CORREÇÃO: Verificar se há mais contatos ANTES de aguardar intervalo
                    # Isso evita aguardar intervalo desnecessário após último contato
                    from asgiref.sync import sync_to_async
                    
                    @sync_to_async
                    def has_more_contacts():
                        from .models import CampaignContact
                        return CampaignContact.objects.filter(
                            campaign=campaign,
                            status='pending'
                        ).exists()
                    
                    has_more = await has_more_contacts()
                    
                    if not has_more:
                        # Não há mais contatos pendentes, verificar se todos foram processados
                        logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} - Nenhum contato pendente restante")
                        await self._process_next_message_async(campaign)  # Processa último contato se houver
                        # Verificar novamente após processar
                        has_more_after = await has_more_contacts()
                        if not has_more_after:
                            # Realmente terminou, encerrar
                            logger.info(f"✅ [AIO-PIKA] Campanha {campaign_id} - Todos os contatos processados, encerrando...")
                            await self._update_campaign_status_async(campaign, 'completed')
                            await self._log_campaign_completed(campaign)
                            break
                    
                    # ✅ CORREÇÃO CRÍTICA: Calcular intervalo ANTES de processar para usar o mesmo valor
                    # Isso garante que o countdown e o sleep usem o mesmo intervalo
                    import random
                    min_interval = campaign.interval_min
                    max_interval = campaign.interval_max
                    random_interval = random.uniform(min_interval, max_interval)
                    
                    # Processar próxima mensagem (passando o intervalo calculado)
                    logger.info(f"🔍 [DEBUG] Processando próxima mensagem da campanha {campaign_id}")
                    logger.info(f"🔍 [DEBUG] Campanha status: {campaign.status}, total_contacts: {campaign.total_contacts}")
                    logger.info(f"⏰ [INTERVAL] Intervalo calculado: {random_interval:.1f}s (min={min_interval}s, max={max_interval}s)")
                    await self._process_next_message_async(campaign, random_interval)
                    
                    # ✅ CORREÇÃO: Só aguardar intervalo se ainda há mais contatos
                    has_more_after_send = await has_more_contacts()
                    if has_more_after_send:
                        # Usar o MESMO intervalo calculado acima
                        logger.info(f"⏰ [INTERVAL] Aguardando {random_interval:.1f}s antes do próximo disparo")
                        await asyncio.sleep(random_interval)
                    else:
                        # Último contato foi enviado, não precisa aguardar
                        logger.info(f"✅ [AIO-PIKA] Último contato enviado, encerrando campanha...")
                        await self._update_campaign_status_async(campaign, 'completed')
                        await self._log_campaign_completed(campaign)
                        break
                    
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
            
            # ✅ SECURITY FIX: Não usar credenciais hardcoded
            rabbitmq_url = settings.RABBITMQ_URL
            # Log seguro (mascarar credenciais)
            import re
            safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)
            
            logger.info(f"🔍 [DEBUG] Criando conexão da thread usando: {safe_url}")
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
    
    async def _process_next_message_async(self, campaign, interval_seconds=None):
        """Processa próxima mensagem da campanha
        
        Args:
            campaign: Campanha a processar
            interval_seconds: Intervalo calculado ANTES do processamento (para garantir sincronia)
        """
        try:
            from asgiref.sync import sync_to_async
            from apps.campaigns.services import RotationService
            
            # ✅ NOVO: Verificar se há instâncias disponíveis ANTES de processar
            @sync_to_async
            def check_available_instances():
                rotation_service = RotationService(campaign)
                available_instances = rotation_service._get_available_instances()
                return len(available_instances) > 0
            
            has_instances = await check_available_instances()
            
            if not has_instances:
                logger.warning(f"⚠️ [AIO-PIKA] Nenhuma instância disponível para campanha {campaign.id} - pausando automaticamente")
                await self._auto_pause_campaign(campaign, "nenhuma instância disponível")
                return
            
            @sync_to_async
            def get_next_contact():
                from .models import CampaignContact
                # ✅ CORREÇÃO: Buscar apenas 'pending', não 'sending' (que já está sendo processado)
                return CampaignContact.objects.filter(
                    campaign=campaign,
                    status='pending'
                ).order_by('created_at').first()
            
            contact = await get_next_contact()

            if not contact:
                # ✅ CORREÇÃO: Verificar se realmente não há mais contatos pendentes
                # (não apenas 'pending', mas também verificar se todos foram enviados)
                @sync_to_async
                def check_all_processed():
                    from .models import CampaignContact
                    # Verificar se há contatos ainda pendentes ou enviando
                    pending_count = CampaignContact.objects.filter(
                        campaign=campaign,
                        status__in=['pending', 'sending']
                    ).count()
                    return pending_count == 0
                
                all_processed = await check_all_processed()
                
                if all_processed:
                    logger.info(f"✅ [AIO-PIKA] Campanha {campaign.id} - Todos os contatos processados")
                    logger.info(f"🔍 [DEBUG] Campanha {campaign.id} - Status atual: {campaign.status}")
                    # Atualizar status da campanha
                    await self._update_campaign_status_async(campaign, 'completed')
                    # Log de encerramento
                    await self._log_campaign_completed(campaign)
                    return
                else:
                    # Ainda há contatos sendo processados, aguardar um pouco
                    logger.info(f"⏳ [AIO-PIKA] Campanha {campaign.id} - Aguardando processamento de contatos em andamento...")
                    await asyncio.sleep(2)  # Aguardar 2s antes de verificar novamente
                    return
            
            logger.info(f"🔍 [DEBUG] Próximo contato encontrado: {contact.id} - Status: {contact.status}")
            
            # Marcar contato como enviando
            await self._update_contact_status_async(contact, 'sending')
            
            # Enviar mensagem (passando o intervalo calculado)
            await self._send_message_async(campaign, contact, interval_seconds)
            
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
        """Atualiza status da campanha de forma assíncrona"""
        try:
            from asgiref.sync import sync_to_async
            from django.utils import timezone
            
            @sync_to_async
            def update_status():
                # Recarregar campanha do banco para garantir dados atualizados
                campaign.refresh_from_db()
                campaign.status = status
                # Se completando, definir completed_at
                if status == 'completed':
                    campaign.completed_at = timezone.now()
                    # Limpar campos de próximo disparo
                    campaign.next_message_scheduled_at = None
                    campaign.next_contact_name = None
                    campaign.next_contact_phone = None
                campaign.save(update_fields=['status', 'completed_at', 'next_message_scheduled_at', 'next_contact_name', 'next_contact_phone'])
                logger.info(f"✅ [AIO-PIKA] Status da campanha {campaign.id} atualizado para {status}")
            
            await update_status()
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao atualizar status da campanha {campaign.id}: {e}")
    
    async def _send_message_async(self, campaign, contact, interval_seconds=None):
        """Envia mensagem de forma assíncrona
        
        Args:
            campaign: Campanha
            contact: Contato da campanha
            interval_seconds: Intervalo calculado no loop principal (para garantir sincronia)
        """
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
            
            # Enviar mensagem (passar interval_seconds para garantir sincronia)
            success = await self._send_whatsapp_message_async(campaign, contact, instance, interval_seconds)
            
            if success:
                # Marcar como enviado
                @sync_to_async
                def mark_sent():
                    contact.status = 'sent'
                    contact.sent_at = timezone.now()
                    contact.save()
                
                await mark_sent()
                
                # ✅ CORREÇÃO: Usar interval_min e interval_max da campanha (não delay_between_messages)
                # O delay já é calculado no loop principal (_process_campaign_async)
                # Aqui não precisamos aguardar novamente, pois o loop já faz isso
                # Mas mantemos um pequeno delay mínimo para evitar sobrecarga
                logger.info(f"✅ [AIO-PIKA] Mensagem enviada com sucesso. Próxima mensagem será processada pelo loop principal.")
                
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
    
    async def _replace_variables(self, message_text, contact):
        """Substitui variáveis na mensagem usando MessageVariableService"""
        from apps.campaigns.services import MessageVariableService
        
        # Se contact é dict, converter para objeto Contact se necessário
        if isinstance(contact, dict):
            # Buscar contato do banco se tiver ID
            contact_id = contact.get('id')
            if contact_id:
                from apps.contacts.models import Contact
                try:
                    contact = Contact.objects.get(id=contact_id)
                except Contact.DoesNotExist:
                    # Fallback: usar dados do dict diretamente
                    from types import SimpleNamespace
                    contact_obj = SimpleNamespace()
                    contact_obj.name = contact.get('name', '')
                    contact_obj.email = contact.get('email', '')
                    contact_obj.city = contact.get('city', '')
                    contact_obj.state = contact.get('state', '')
                    contact_obj.referred_by = contact.get('referred_by', '')
                    contact_obj.last_purchase_value = contact.get('last_purchase_value')
                    contact_obj.last_purchase_date = contact.get('last_purchase_date')
                    contact_obj.custom_fields = contact.get('custom_fields', {})
                    contact = contact_obj
        
        return MessageVariableService.render_message(message_text, contact)
    
    async def _send_typing_presence(self, instance, contact_phone, typing_seconds):
        """Envia status 'digitando' antes da mensagem para parecer mais humano"""
        try:
            from apps.notifications.models import WhatsAppInstance
            if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
                await asyncio.sleep(typing_seconds)
                return
            from apps.connections.models import EvolutionConnection
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def get_evolution_server():
                return EvolutionConnection.objects.filter(is_active=True).first()
            
            evolution_server = await get_evolution_server()
            api_key = instance.api_key or (evolution_server.api_key if evolution_server else None)
            
            if not api_key:
                logger.error(f"❌ [PRESENCE] Nenhuma API key disponível para instância {instance.instance_name}")
                logger.error(f"   Instance API Key: {instance.api_key}")
                logger.error(f"   Evolution Server API Key: {evolution_server.api_key if evolution_server else 'N/A'}")
                return  # Não tentar enviar se não houver API key
            
            # ✅ DEBUG: Log detalhado das credenciais sendo usadas
            logger.info("="*80)
            logger.info(f"🔐 [PRESENCE DEBUG] Credenciais sendo usadas:")
            logger.info(f"   Instância ID: {instance.id}")
            logger.info(f"   Instance Name: {instance.instance_name}")
            logger.info(f"   Friendly Name: {instance.friendly_name}")
            logger.info(f"   API URL: {instance.api_url}")
            logger.info(f"   Instance API Key: {instance.api_key or 'None (usando global)'}")
            logger.info(f"   API Key usada (primeiros 10): {api_key[:10] if api_key else 'None'}...")
            logger.info(f"   API Key usada (últimos 4): ...{api_key[-4:] if api_key and len(api_key) > 4 else 'None'}")
            logger.info(f"   Phone Number: {instance.phone_number}")
            logger.info(f"   Connection State: {instance.connection_state}")
            logger.info("="*80)
            
            presence_url = f"{instance.api_url}/chat/sendPresence/{instance.instance_name}"
            # 🔧 CORREÇÃO: Evolution API espera delay e presence direto no root (não dentro de options)
            presence_data = {
                "number": contact_phone,
                "delay": int(typing_seconds * 1000),  # Converter para milissegundos
                "presence": "composing"
            }
            headers = {
                "Content-Type": "application/json",
                "apikey": api_key  # ✅ CREDENCIAL USADA: instance.api_key ou EVOLUTION_API_KEY global como fallback
            }
            
            logger.info(f"📤 [PRESENCE] URL: {presence_url}")
            logger.info(f"📤 [PRESENCE] Headers: apikey={api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else api_key}")
            logger.info(f"📤 [PRESENCE] Body: {presence_data}")
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(presence_url, json=presence_data, headers=headers, timeout=10)
            )
            
            # ✅ CORREÇÃO: Verificar status antes de logar sucesso (200 e 201 são sucesso)
            if response.status_code in [200, 201]:
                logger.info(f"✍️ [PRESENCE] Status 'digitando' enviado para {contact_phone} por {typing_seconds}s")
                # Aguardar o tempo de digitação
                await asyncio.sleep(typing_seconds)
            elif response.status_code == 401:
                logger.error("="*80)
                logger.error(f"❌ [PRESENCE] Erro 401 (Unauthorized)")
                logger.error(f"   URL: {presence_url}")
                logger.error(f"   API Key usada: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else api_key}")
                logger.error(f"   Instance API Key: {instance.api_key or 'None (usando global)'}")
                logger.error(f"   Instance Name: {instance.instance_name}")
                logger.error(f"   Response: {response.text[:200] if hasattr(response, 'text') else 'N/A'}")
                logger.error("="*80)
                # Não bloquear envio se presence falhar por 401
            else:
                logger.warning(f"⚠️ [PRESENCE] Erro {response.status_code} ao enviar presence para {contact_phone}")
                logger.warning(f"   Response: {response.text[:200] if hasattr(response, 'text') else 'N/A'}")
                # Não bloquear envio se presence falhar
            
        except Exception as e:
            logger.warning(f"⚠️ [PRESENCE] Erro ao enviar status 'digitando': {e}")
            logger.warning(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")
            # Não falhar o envio se o presence falhar

    async def _send_whatsapp_message_async(self, campaign, contact, instance, interval_seconds=None):
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
                
                # ✅ CORREÇÃO CRÍTICA: Usar rotação de mensagens (menor times_used primeiro)
                from asgiref.sync import sync_to_async
                from django.db.models import F
                from apps.campaigns.models import CampaignMessage
                import logging
                rotation_logger = logging.getLogger(__name__)
                
                @sync_to_async
                def get_message_with_rotation():
                    # ✅ DEBUG: Listar TODAS as mensagens antes da seleção
                    # ✅ CORREÇÃO: Removido filtro is_active (CampaignMessage não tem esse campo)
                    all_messages = CampaignMessage.objects.filter(
                        campaign=campaign
                    ).order_by('order').values('id', 'order', 'times_used', 'content')
                    
                    rotation_logger.info(f"📋 [ROTAÇÃO DEBUG] Todas as mensagens disponíveis:")
                    for msg in all_messages:
                        rotation_logger.info(f"   - Mensagem ordem={msg['order']}, times_used={msg['times_used']}, id={str(msg['id'])[:8]}..., content={msg['content'][:50]}...")
                    
                    # ✅ CORREÇÃO CRÍTICA: Buscar mensagem com menor uso usando query atômica
                    # Ordenar por times_used ASC (menor primeiro), depois por order ASC (ordem de criação)
                    # ✅ CORREÇÃO: Removido filtro is_active (CampaignMessage não tem esse campo)
                    message = CampaignMessage.objects.filter(
                        campaign=campaign
                    ).order_by('times_used', 'order').first()
                    
                    if not message:
                        rotation_logger.error(f"❌ [ROTAÇÃO] Nenhuma mensagem ativa encontrada para campanha {campaign.id}")
                        return None
                    
                    # ✅ DEBUG: Log da mensagem selecionada ANTES do incremento
                    times_used_before = message.times_used
                    rotation_logger.info(f"🎯 [ROTAÇÃO] Mensagem selecionada ANTES incremento: ordem={message.order}, times_used={times_used_before}, id={str(message.id)[:8]}..., content={message.content[:50]}...")
                    
                    # ✅ CORREÇÃO CRÍTICA: Incrementar times_used ANTES de enviar (atomicamente)
                    # Isso garante que a próxima seleção já veja o valor atualizado
                    rows_updated = CampaignMessage.objects.filter(id=message.id).update(times_used=F('times_used') + 1)
                    rotation_logger.info(f"✅ [ROTAÇÃO] Incremento executado: rows_updated={rows_updated}")
                    
                    # Recarregar mensagem para ter times_used atualizado
                    message.refresh_from_db()
                    
                    # ✅ DEBUG: Log DEPOIS do incremento
                    rotation_logger.info(f"🔄 [ROTAÇÃO] DEPOIS incremento - Mensagem: ordem={message.order}, times_used={message.times_used} (era {times_used_before})")
                    
                    # ✅ CORREÇÃO: Salvar message_used no campaign_contact ANTES de enviar
                    contact.message_used = message
                    contact.save(update_fields=['message_used'])
                    
                    rotation_logger.info(f"📤 [ENVIO] Preparando envio - Contato: {contact.contact.name}, Mensagem ordem={message.order}, times_used={message.times_used}, content={message.content[:50]}...")
                    
                    return message
                
                message = await get_message_with_rotation()
                
                if not message:
                    logger.error(f"❌ [AIO-PIKA] Nenhuma mensagem encontrada para campanha {campaign.id}")
                    return False
                
                # ✅ CORREÇÃO CRÍTICA: Marcar início do processo para calcular tempo real decorrido
                import time
                process_start_time = time.time()
                
                # 🎯 HUMANIZAÇÃO: Enviar status "digitando" com tempo aleatório entre 5s e 10s
                typing_seconds = random.uniform(5.0, 10.0)
                await self._send_typing_presence(instance, contact_phone, typing_seconds)
                
                # ✅ CORREÇÃO: Passar objeto Contact completo para renderizar variáveis
                # Isso permite acesso a todos os campos padrão + custom_fields
                @sync_to_async
                def get_contact_obj():
                    # Recarregar contato do banco para garantir dados atualizados
                    contact.contact.refresh_from_db()
                    return contact.contact
                
                contact_obj = await get_contact_obj()
                message_text = await self._replace_variables(message.content, contact_obj)
                
                # Preparar dados da mensagem
                from apps.notifications.whatsapp_providers import get_sender
                from apps.notifications.models import WhatsAppInstance, WhatsAppTemplate
                from django.db.models import Q
                from asgiref.sync import sync_to_async

                sender = await sync_to_async(get_sender)(instance)
                if not sender:
                    logger.error(f"❌ [AIO-PIKA] get_sender retornou None para instância {instance.instance_name}")
                    raise Exception(f"Provider não disponível para instância {instance.instance_name}")

                is_meta = getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD
                if is_meta:
                    wa_template = await sync_to_async(
                        lambda: WhatsAppTemplate.objects.filter(
                            tenant=instance.tenant,
                            is_active=True,
                        ).filter(Q(wa_instance=instance) | Q(wa_instance__isnull=True)).order_by('name').first()
                    )()
                    if not wa_template:
                        raise Exception(
                            "Campanhas com instância API Meta exigem um template aprovado. "
                            "Cadastre um template em Notificações > Templates WhatsApp."
                        )

                def do_send():
                    if is_meta:
                        params = list(wa_template.body_parameters_default) if wa_template.body_parameters_default else [message_text]
                        return sender.send_template(
                            contact_phone,
                            wa_template.template_id,
                            wa_template.language_code or 'pt_BR',
                            params,
                        )
                    return sender.send_text(contact_phone, message_text)

                loop = asyncio.get_event_loop()
                ok, response_data = await loop.run_in_executor(None, do_send)

                if ok:
                    logger.info(f"✅ [AIO-PIKA] Mensagem enviada com sucesso para {contact_phone} (tentativa {attempt})")
                    message_id = response_data.get('messageId') or (response_data.get('key') or {}).get('id')
                    if not message_id and response_data.get('messages'):
                        msg_list = response_data.get('messages') or []
                        if msg_list and isinstance(msg_list[0], dict):
                            message_id = msg_list[0].get('id')
                    # ✅ CORREÇÃO CRÍTICA: Criar log ANTES de salvar message_id para evitar race condition
                    await self._log_message_sent(campaign, contact, instance, message_id, contact_phone, message_text)
                    if message_id:
                        @sync_to_async
                        def save_message_id():
                            contact.whatsapp_message_id = message_id
                            contact.status = 'sent'
                            contact.sent_at = contact.sent_at or timezone.now()
                            contact.save(update_fields=['whatsapp_message_id', 'status', 'sent_at'])
                            logger.info(f"✅ [AIO-PIKA] whatsapp_message_id salvo: {message_id} para contact {contact.id}")
                        await save_message_id()
                        await self._create_chat_message(campaign, contact, instance, message_text, message_id, contact_phone)
                    else:
                        logger.warning(f"⚠️ [AIO-PIKA] message_id não encontrado na resposta para {contact_phone}")
                        logger.warning(f"   Response data: {response_data}")
                    # ✅ CORREÇÃO CRÍTICA: Calcular próximo disparo DEPOIS do envio bem-sucedido
                    process_elapsed_time = time.time() - process_start_time
                    @sync_to_async
                    def update_next_contact_info():
                            import random
                            from django.utils import timezone
                            from datetime import timedelta
                            from apps.campaigns.models import CampaignContact
                            from apps.campaigns.services import RotationService
                            
                            # ✅ CORREÇÃO: Usar interval_seconds do escopo externo (closure)
                            nonlocal interval_seconds
                            
                            # Buscar próximo contato pendente
                            next_campaign_contact = CampaignContact.objects.filter(
                                campaign=campaign,
                                status__in=['pending', 'sending']
                            ).select_related('contact').first()
                            
                            if next_campaign_contact:
                                campaign.next_contact_name = next_campaign_contact.contact.name
                                campaign.next_contact_phone = next_campaign_contact.contact.phone
                                
                                # Obter próxima instância usando o serviço de rotação
                                rotation_service = RotationService(campaign)
                                next_instance = rotation_service.select_next_instance()
                                if next_instance:
                                    campaign.next_instance_name = next_instance.friendly_name
                                else:
                                    campaign.next_instance_name = None
                                
                                # ✅ CORREÇÃO CRÍTICA: Usar o MESMO intervalo calculado no loop principal
                                # Isso garante sincronia entre countdown e sleep
                                if interval_seconds is None:
                                    # Fallback: calcular intervalo se não foi passado
                                    min_interval = campaign.interval_min
                                    max_interval = campaign.interval_max
                                    interval_seconds = random.uniform(min_interval, max_interval)
                                    rotation_logger.warning(f"⚠️ [AGENDAMENTO] Intervalo não foi passado, calculando novo: {interval_seconds:.1f}s")
                                
                                # Calcular baseado no momento ATUAL (depois do envio bem-sucedido)
                                # O countdown será: intervalo completo a partir de AGORA
                                # O loop principal vai aguardar esse MESMO intervalo antes de processar a próxima mensagem
                                now = timezone.now()
                                next_scheduled = now + timedelta(seconds=interval_seconds)
                                
                                campaign.next_message_scheduled_at = next_scheduled
                                
                                rotation_logger.info(f"⏰ [AGENDAMENTO] Próximo disparo calculado DEPOIS do envio: {next_scheduled} (em {interval_seconds:.1f}s a partir de agora)")
                                rotation_logger.info(f"   Tempo de processamento decorrido: {process_elapsed_time:.2f}s")
                                rotation_logger.info(f"   O loop principal aguardará {interval_seconds:.1f}s antes de processar a próxima mensagem")
                            else:
                                # Não há mais contatos pendentes
                                campaign.next_contact_name = None
                                campaign.next_contact_phone = None
                                campaign.next_instance_name = None
                                campaign.next_message_scheduled_at = None
                            
                            # ✅ CORREÇÃO: Salvar campos de próximo contato incluindo next_message_scheduled_at
                            campaign.save(update_fields=[
                                'next_contact_name', 'next_contact_phone', 'next_instance_name',
                                'next_message_scheduled_at'  # Pode ser None se não há mais contatos
                            ])
                            
                            rotation_logger.info(f"✅ [PRÓXIMO CONTATO] Atualizado: {campaign.next_contact_name} ({campaign.next_contact_phone})")
                            if campaign.next_message_scheduled_at:
                                rotation_logger.info(f"⏰ [AIO-PIKA] Próximo disparo agendado para: {campaign.next_message_scheduled_at}")
                            
                            # ✅ NOVO: Broadcast via WebSocket para atualizar frontend em tempo real
                            # Nota: Esta função é sync (wrapped com @sync_to_async), então fazemos broadcast de forma síncrona
                            try:
                                from channels.layers import get_channel_layer
                                from asgiref.sync import async_to_sync
                                
                                channel_layer = get_channel_layer()
                                if channel_layer:
                                    tenant_group = f"chat_tenant_{campaign.tenant.id}"
                                    
                                    # Calcular countdown
                                    from django.utils import timezone
                                    now = timezone.now()
                                    countdown_seconds = 0
                                    if campaign.next_message_scheduled_at and campaign.next_message_scheduled_at > now:
                                        delta = campaign.next_message_scheduled_at - now
                                        countdown_seconds = int(delta.total_seconds())
                                    
                                    message = {
                                        'type': 'campaign_update',
                                        'payload': {
                                            'campaign_id': str(campaign.id),
                                            'campaign_name': campaign.name,
                                            'type': 'next_contact_updated',
                                            'next_contact_name': campaign.next_contact_name,
                                            'next_contact_phone': campaign.next_contact_phone,
                                            'next_instance_name': campaign.next_instance_name,
                                            'next_message_scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                                            'countdown_seconds': countdown_seconds,
                                            'timestamp': timezone.now().isoformat()
                                        }
                                    }
                                    
                                    async_to_sync(channel_layer.group_send)(tenant_group, message)
                                    rotation_logger.info(f"📡 [WEBSOCKET] Broadcast enviado: próximo contato atualizado para campanha {campaign.id}")
                            except Exception as e:
                                rotation_logger.error(f"❌ [WEBSOCKET] Erro ao enviar broadcast: {e}", exc_info=True)
                    await update_next_contact_info()
                    logger.info(f"✅ [AIO-PIKA] Próximo contato atualizado com sucesso")
                    return True
                else:
                    error_msg = response_data.get('error', str(response_data))[:200]
                    logger.error(f"❌ [AIO-PIKA] Provider retornou erro (tentativa {attempt}): {error_msg}")
                    if 'instance' in error_msg.lower() or 'disconnected' in error_msg.lower():
                        await self._auto_pause_campaign(campaign, f"instância desconectada: {error_msg}")
                        return False
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.info(f"⏳ [AIO-PIKA] Tentando novamente em {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    await self._log_message_failed(
                        campaign, contact, instance, error_msg, contact_phone,
                        request_data={'text': message_text},
                        response_data=response_data,
                        http_status=response_data.get('status_code')
                    )
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
    
    async def _create_chat_message(self, campaign, contact, instance, message_text, whatsapp_message_id, contact_phone):
        """
        Cria mensagem no chat para que apareça na conversa.
        Busca ou cria a conversa e então cria a mensagem.
        """
        try:
            from asgiref.sync import sync_to_async
            from apps.chat.models import Conversation, Message
            from apps.contacts.signals import normalize_phone_for_search
            from django.db.models import Q
            from django.utils import timezone
            
            @sync_to_async
            def create_message_in_chat():
                # Normalizar telefone para busca consistente
                normalized_phone = normalize_phone_for_search(contact_phone)
                
                # Buscar ou criar conversa
                existing_conversation = Conversation.objects.filter(
                    Q(tenant=campaign.tenant) &
                    (Q(contact_phone=normalized_phone) | Q(contact_phone=contact_phone))
                ).first()
                
                if existing_conversation:
                    conversation = existing_conversation
                    # Atualizar telefone para formato normalizado se necessário
                    if conversation.contact_phone != normalized_phone:
                        conversation.contact_phone = normalized_phone
                        conversation.save(update_fields=['contact_phone'])
                else:
                    # Criar nova conversa
                    # Buscar nome do contato
                    contact_name = contact.contact.name if hasattr(contact, 'contact') and contact.contact else contact_phone
                    
                    # Usar departamento padrão da instância se disponível
                    default_department = instance.default_department if hasattr(instance, 'default_department') else None
                    
                    conversation = Conversation.objects.create(
                        tenant=campaign.tenant,
                        contact_phone=normalized_phone,
                        contact_name=contact_name,
                        department=default_department,
                        status='open' if default_department else 'pending',
                        conversation_type='individual',
                        instance_name=instance.instance_name,
                    )
                    logger.info(f"✅ [CHAT] Nova conversa criada para campanha: {normalized_phone}")
                
                # Criar mensagem no chat
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,  # Mensagem de campanha não tem sender (sistema)
                    content=message_text,
                    direction='outgoing',
                    status='sent',
                    is_internal=False,
                    message_id=whatsapp_message_id,  # ID da mensagem WhatsApp para rastreamento
                    metadata={
                        'from_campaign': True,
                        'campaign_id': str(campaign.id),
                        'campaign_name': campaign.name,
                        'instance_name': instance.instance_name,
                    }
                )
                
                # Atualizar timestamp da última mensagem da conversa
                conversation.update_last_message()
                
                logger.info(f"✅ [CHAT] Mensagem criada no chat: conversation_id={conversation.id}, message_id={message.id}")
                return message
            
            await create_message_in_chat()
            
        except Exception as e:
            # Não falhar o envio da campanha se houver erro ao criar mensagem no chat
            logger.error(f"❌ [CHAT] Erro ao criar mensagem no chat: {e}", exc_info=True)
    
    async def _log_message_sent(self, campaign, contact, instance, message_id, contact_phone, message_text):
        """Log de mensagem enviada com todas as informações incluindo o texto da mensagem"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def create_log():
                # Buscar dados do contato
                contact_name = contact.contact.name if hasattr(contact, 'contact') else 'Desconhecido'
                
                CampaignLog.objects.create(
                    campaign=campaign,
                    campaign_contact=contact,
                    instance=instance,
                    log_type='message_sent',  # ✅ CORRIGIDO: era event_type
                    severity='info',
                    message=f'Mensagem enviada para {contact_name} ({contact_phone})',
                    details={
                        'contact_id': str(contact.contact.id if hasattr(contact, 'contact') else None),
                        'contact_name': contact_name,
                        'phone': contact_phone,
                        'instance_id': instance.instance_name,
                        'instance_name': instance.friendly_name,
                        'message_id': message_id,
                        'message_text': message_text,  # ✅ TEXTO DA MENSAGEM
                        'sent_at': timezone.now().isoformat()
                    }
                )
            
            await create_log()
            logger.info(f"✅ [LOG] Log de envio criado para {contact_phone}")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar log de mensagem enviada: {e}")
            import traceback
            logger.error(f"🔍 [DEBUG] Traceback: {traceback.format_exc()}")
    
    def _extract_error_message(self, response_data, http_status=None, raw_response=None):
        """
        Extrai mensagem de erro descritiva e amigável da resposta da API.
        """
        # Dicionário de mensagens amigáveis para códigos HTTP comuns
        http_messages = {
            400: "Requisição inválida - verifique os dados enviados",
            401: "Não autorizado - verifique as credenciais da API",
            403: "Acesso negado - verifique as permissões",
            404: "Recurso não encontrado - instância ou endpoint não existe",
            429: "Muitas requisições - limite de taxa excedido, aguarde antes de tentar novamente",
            500: "Erro interno do servidor - problema temporário na API",
            502: "Servidor indisponível - gateway ou proxy com problema",
            503: "Serviço indisponível - servidor temporariamente fora do ar",
        }
        
        # Tentar extrair mensagem da resposta JSON
        error_message = None
        error_details = []
        
        if isinstance(response_data, dict):
            # ✅ MELHORIA: Verificar TODOS os campos possíveis de erro da Evolution API
            error_message = (
                response_data.get('message') or
                response_data.get('error') or
                response_data.get('errorMessage') or
                response_data.get('error_description') or
                response_data.get('detail') or
                response_data.get('reason') or  # Novo campo
                response_data.get('code') or    # Novo campo
                response_data.get('data')       # Novo campo (pode ser string ou dict)
            )
            
            # Se error_message é um dict, tentar extrair mensagem dele
            if isinstance(error_message, dict):
                error_message = error_message.get('message') or error_message.get('error') or str(error_message)
            
            # Coletar detalhes adicionais para incluir na mensagem
            if response_data.get('code'):
                error_details.append(f"Código: {response_data['code']}")
            if response_data.get('reason'):
                error_details.append(f"Motivo: {response_data['reason']}")
            if response_data.get('data'):
                data_str = str(response_data['data'])[:100] if not isinstance(response_data['data'], str) else response_data['data'][:100]
                error_details.append(f"Dados: {data_str}")
        
        # Se não encontrou mensagem na resposta, usar mensagem HTTP padrão
        if not error_message and http_status:
            error_message = http_messages.get(http_status, f"Erro HTTP {http_status}")
        
        # Se ainda não tem mensagem, usar resposta raw (limitada)
        if not error_message and raw_response:
            # Limitar tamanho e remover quebras de linha
            error_message = raw_response[:300].replace('\n', ' ').replace('\r', ' ').strip()
            if len(raw_response) > 300:
                error_message += "..."
        
        # Fallback final
        if not error_message:
            error_message = "Erro desconhecido ao enviar mensagem"
        
        # Adicionar detalhes se disponíveis
        if error_details:
            error_message = f"{error_message} - {', '.join(error_details)}"
        
        # Adicionar código HTTP se disponível
        if http_status:
            error_message = f"{error_message} (HTTP {http_status})"
        
        return error_message
    
    async def _log_message_failed(self, campaign, contact, instance, error_msg, contact_phone, request_data=None, response_data=None, http_status=None):
        """Log de mensagem falhada com todas as informações"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def create_log():
                # Buscar dados do contato
                contact_name = contact.contact.name if hasattr(contact, 'contact') else 'Desconhecido'
                
                CampaignLog.objects.create(
                    campaign=campaign,
                    campaign_contact=contact,
                    instance=instance,
                    log_type='message_failed',
                    severity='error',
                    message=f'Falha ao enviar para {contact_name} ({contact_phone}): {error_msg}',
                    details={
                        'contact_id': str(contact.contact.id if hasattr(contact, 'contact') else None),
                        'contact_name': contact_name,
                        'phone': contact_phone,
                        'instance_id': instance.instance_name,
                        'instance_name': instance.friendly_name,
                        'error': error_msg,  # ✅ Mensagem completa e descritiva
                        'failed_at': timezone.now().isoformat(),
                        # ✅ MELHORIA: Incluir dados completos para diagnóstico
                        'request_data': request_data,
                        'response_data': response_data,
                        'http_status': http_status
                    },
                    request_data=request_data,
                    response_data=response_data,
                    http_status=http_status
                )
            
            await create_log()
            logger.info(f"✅ [LOG] Log de falha criado para {contact_phone}: {error_msg}")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar log de mensagem falhada: {e}")
            import traceback
            logger.error(f"🔍 [DEBUG] Traceback: {traceback.format_exc()}")
    
    async def _log_campaign_completed(self, campaign):
        """Log de campanha concluída com estatísticas"""
        try:
            from asgiref.sync import sync_to_async
            
            @sync_to_async
            def create_log():
                CampaignLog.objects.create(
                    campaign=campaign,
                    log_type='completed',
                    severity='info',
                    message=f'Campanha "{campaign.name}" concluída com sucesso',
                    details={
                        'total_contacts': campaign.total_contacts,
                        'messages_sent': campaign.messages_sent,
                        'messages_delivered': campaign.messages_delivered,
                        'messages_read': campaign.messages_read,
                        'messages_failed': campaign.messages_failed,
                        'success_rate': campaign.success_rate,
                        'read_rate': campaign.read_rate,
                        'completed_at': timezone.now().isoformat()
                    }
                )
            
            await create_log()
            logger.info(f"✅ [LOG] Log de conclusão criado para campanha {campaign.name}")
            
        except Exception as e:
            logger.error(f"❌ [AIO-PIKA] Erro ao criar log de conclusão: {e}")
            import traceback
            logger.error(f"🔍 [DEBUG] Traceback: {traceback.format_exc()}")
    
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