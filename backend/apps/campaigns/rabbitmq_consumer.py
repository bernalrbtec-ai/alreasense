"""
Consumer RabbitMQ Puro - Sistema de Campanhas
Implementa processamento robusto sem Celery
"""
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
import pika
import requests

from .models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """Consumer RabbitMQ para processamento de campanhas"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.running = False
        self.consumer_threads = {}
        self._connect()
    
    def _connect(self):
        """Estabelece conexão com RabbitMQ com retry automático"""
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                rabbitmq_url = getattr(settings, 'RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
                
                # Configurações de conexão robustas
                connection_params = pika.URLParameters(rabbitmq_url)
                connection_params.heartbeat = 600  # 10 minutos
                connection_params.blocked_connection_timeout = 300  # 5 minutos
                connection_params.socket_timeout = 30
                connection_params.retry_delay = 2
                connection_params.connection_attempts = 3
                
                self.connection = pika.BlockingConnection(connection_params)
                self.channel = self.connection.channel()
                
                # Configurar exchanges e filas
                self._setup_queues()
                
                logger.info(f"✅ [RABBITMQ] Conectado com sucesso (tentativa {attempt})")
                return
                
            except Exception as e:
                error_msg = str(e)
                # Tratar erro específico do pika 1.3.2
                if "pop from an empty deque" in error_msg or "IndexError" in error_msg:
                    logger.error(f"🐛 [PIKA_BUG] Erro conhecido do pika (tentativa {attempt}/{max_retries}): {e}")
                    logger.info("🔧 [PIKA_BUG] Tentando reconexão devido a bug do pika...")
                else:
                    logger.error(f"❌ [RABBITMQ] Erro na conexão (tentativa {attempt}/{max_retries}): {e}")
                
                if attempt < max_retries:
                    logger.info(f"🔄 [RABBITMQ] Tentando novamente em {retry_delay}s...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ [RABBITMQ] Falha após {max_retries} tentativas")
                    raise
    
    def _check_connection(self):
        """Verifica se a conexão está ativa e reconecta se necessário"""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("⚠️ [RABBITMQ] Conexão perdida, reconectando...")
                self._connect()
            elif not self.channel or self.channel.is_closed:
                logger.warning("⚠️ [RABBITMQ] Canal perdido, reconectando...")
                self._connect()
        except Exception as e:
            error_msg = str(e)
            if "pop from an empty deque" in error_msg or "IndexError" in error_msg:
                logger.error(f"🐛 [PIKA_BUG] Erro conhecido do pika ao verificar conexão: {e}")
            else:
                logger.error(f"❌ [RABBITMQ] Erro ao verificar conexão: {e}")
            
            try:
                self._connect()
            except Exception as reconnect_error:
                logger.error(f"❌ [RABBITMQ] Falha ao reconectar: {reconnect_error}")

    def _setup_queues(self):
        """Configura filas e exchanges"""
        # Exchange principal
        self.channel.exchange_declare(
            exchange='campaigns',
            exchange_type='topic',
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
        
        for queue in queues:
            self.channel.queue_declare(queue=queue, durable=True)
            self.channel.queue_bind(
                exchange='campaigns',
                queue=queue,
                routing_key=queue
            )
    
    def start_campaign(self, campaign_id: str):
        """Inicia processamento de uma campanha"""
        try:
            logger.info(f"🚀 [START] Iniciando campanha {campaign_id}")
            
            # Verificar conexão antes de iniciar campanha
            logger.info(f"🔍 [START] Verificando conexão RabbitMQ...")
            self._check_connection()
            logger.info(f"✅ [START] Conexão RabbitMQ OK")
            
            campaign = Campaign.objects.get(id=campaign_id)
            logger.info(f"📋 [START] Campanha encontrada: {campaign.name} (status: {campaign.status})")
            
            if campaign.status not in ['draft', 'running']:
                logger.warning(f"⚠️ [CONSUMER] Campanha {campaign.name} status inválido: {campaign.status}")
                return False
            
            # Verificar se tem contatos
            logger.info(f"🔍 [START] Verificando contatos pendentes...")
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).count()
            
            total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
            logger.info(f"🔍 [CONSUMER] Campanha {campaign.name}: {pending_contacts} pendentes de {total_contacts} total")
            
            if pending_contacts == 0:
                logger.warning(f"⚠️ [CONSUMER] Campanha {campaign.name} não possui contatos pendentes")
                return False
            
            # Verificar instâncias selecionadas
            logger.info(f"🔍 [START] Verificando instâncias selecionadas...")
            selected_instances = campaign.instances.filter(is_active=True).count()
            logger.info(f"📱 [START] Instâncias ativas selecionadas: {selected_instances}")
            
            if selected_instances == 0:
                logger.error(f"❌ [START] Nenhuma instância ativa selecionada para campanha {campaign.name}")
                return False
            
            # Atualizar status
            logger.info(f"📝 [START] Atualizando status para 'running'...")
            campaign.status = 'running'
            campaign.save(update_fields=['status'])
            logger.info(f"✅ [START] Status atualizado com sucesso")
            
            # Log de início
            logger.info(f"📝 [START] Criando log de início...")
            CampaignLog.log_campaign_started(campaign)
            logger.info(f"✅ [START] Log criado com sucesso")
            
            # 🚀 GATILHO: Campanha iniciada - frontend receberá dados iniciais
            logger.info(f"📡 [WEBSOCKET] Enviando gatilho 'campaign_started' para campanha {campaign.name}")
            self._send_websocket_update(campaign, 'campaign_update', {
                'event': 'campaign_started',
                'total_contacts': total_contacts,
                'pending_contacts': pending_contacts
            })
            logger.info(f"✅ [WEBSOCKET] Gatilho 'campaign_started' enviado com sucesso")
            
            # Criar fila específica da campanha
            logger.info(f"📋 [START] Criando fila RabbitMQ...")
            queue_name = f"campaign.{campaign_id}.messages"
            self.channel.queue_declare(queue=queue_name, durable=True)
            logger.info(f"✅ [START] Fila declarada: {queue_name}")
            
            self.channel.queue_bind(
                exchange='campaigns',
                queue=queue_name,
                routing_key=queue_name
            )
            logger.info(f"✅ [START] Fila vinculada ao exchange")
            
            # Adicionar mensagens à fila
            logger.info(f"📤 [START] Populando fila com mensagens...")
            self._populate_campaign_queue(campaign)
            logger.info(f"✅ [START] Fila populada com sucesso")
            
            # Iniciar consumer para esta campanha
            logger.info(f"🎯 [START] Iniciando consumer...")
            self._start_campaign_consumer(campaign_id)
            logger.info(f"✅ [START] Consumer iniciado")
            
            logger.info(f"🚀 [CONSUMER] Campanha {campaign.name} iniciada com sucesso!")
            return True
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [CONSUMER] Campanha {campaign_id} não encontrada")
            return False
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao iniciar campanha: {e}")
            return False
    
    def _populate_campaign_queue(self, campaign: Campaign):
        """Popula fila com TODOS os contatos na ORDEM DE CRIAÇÃO - ROTAÇÃO PERFEITA"""
        try:
            # Buscar TODOS os contatos pendentes na ORDEM DE CRIAÇÃO
            contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).select_related('contact').order_by('created_at')  # ← ORDEM DE CRIAÇÃO
            
            if not contacts.exists():
                logger.warning(f"⚠️ [CONSUMER] Nenhum contato pendente para campanha {campaign.name}")
                return
            
            # 🎯 USAR APENAS INSTÂNCIAS SELECIONADAS NA CAMPANHA
            instances = campaign.instances.filter(is_active=True).order_by('created_at')
            
            if not instances.exists():
                logger.error(f"❌ [CONSUMER] Nenhuma instância selecionada ativa para campanha {campaign.name}")
                return
            
            queue_name = f"campaign.{campaign.id}.messages"
            instances_list = list(instances)
            instance_count = len(instances_list)
            
            logger.info(f"🔄 [ROTATION] Populando fila: {contacts.count()} contatos na ORDEM DE CRIAÇÃO, {instance_count} instâncias")
            
            # Verificar conexão antes de publicar
            self._check_connection()
            
            # Processar CADA contato na ordem de criação com rotação sequencial
            for i, contact in enumerate(contacts):
                # Calcular delay aleatório para este contato
                delay_seconds = random.randint(campaign.interval_min, campaign.interval_max)
                
                # Calcular índice da instância (round robin) baseado na ORDEM DE CRIAÇÃO
                instance_index = i % instance_count  # ← ROTAÇÃO PERFEITA baseada na ordem
                selected_instance = instances_list[instance_index]
                
                logger.info(f"🎯 [ROTATION] Contato {i+1} (ordem criação): selecionando instância {instance_index} = {selected_instance.friendly_name} (ID: {selected_instance.id})")
                
                # Criar mensagem com rotação pré-calculada
                message = {
                    'campaign_id': str(campaign.id),
                    'contact_id': str(contact.contact.id),
                    'campaign_contact_id': str(contact.id),
                    'contact_phone': contact.contact.phone,
                    'message_content': self._get_message_content(campaign, i),  # ← ROTAÇÃO DE MENSAGENS baseada na posição
                    'scheduled_delay_seconds': delay_seconds,
                    'created_at': timezone.now().isoformat(),
                    'campaign_settings': {
                        'interval_min': campaign.interval_min,
                        'interval_max': campaign.interval_max,
                        'rotation_mode': campaign.rotation_mode,
                        'selected_instances': [str(inst.id) for inst in instances_list],
                        'instance_rotation_index': instance_index,  # ← ROTAÇÃO PRÉ-CALCULADA
                        'selected_instance_id': str(selected_instance.id)  # ← INSTÂNCIA ESPECÍFICA
                    }
                }
                
                logger.info(f"📝 [MESSAGE] Mensagem criada para {contact.contact.name}: selected_instance_id = {str(selected_instance.id)}")
                
                # Publicar mensagem (todas na ordem correta)
                self.channel.basic_publish(
                    exchange='campaigns',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistir mensagem
                        timestamp=int(time.time())
                    )
                )
                
                logger.info(f"📤 [QUEUE] Contato {i+1}/{contacts.count()}: {contact.contact.name} → {selected_instance.friendly_name} (delay: {delay_seconds}s)")
            
            logger.info(f"✅ [ROTATION] Fila populada: {contacts.count()} mensagens na ORDEM DE CRIAÇÃO com rotação perfeita")
            
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao popular fila: {e}")
    
    def _start_campaign_consumer(self, campaign_id: str):
        """Inicia consumer para uma campanha específica"""
        if campaign_id in self.consumer_threads:
            logger.warning(f"⚠️ [CONSUMER] Consumer já ativo para campanha {campaign_id}")
            return
        
        def consumer_callback(ch, method, properties, body):
            try:
                message_data = json.loads(body)
                success = self._process_message(message_data)
                
                # ✅ SEMPRE confirmar mensagem (nunca travar a fila)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
                if not success:
                    logger.warning(f"⚠️ [CONSUMER] Mensagem processada com falha, mas fila continua")
                    
            except Exception as e:
                logger.error(f"❌ [CONSUMER] Erro crítico ao processar mensagem: {e}")
                # ✅ SEMPRE confirmar mensagem para não travar a fila
                try:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"✅ [CONSUMER] Mensagem confirmada mesmo com erro - fila continua")
                except Exception as ack_error:
                    logger.error(f"❌ [CONSUMER] Erro ao confirmar mensagem: {ack_error}")
                    # Forçar nack apenas se ack falhar
                    try:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    except:
                        pass
        
        def start_consuming():
            try:
                queue_name = f"campaign.{campaign_id}.messages"
                
                # Configurar QoS
                self.channel.basic_qos(prefetch_count=1)
                
                # Iniciar consumer
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=consumer_callback,
                    auto_ack=False
                )
                
                logger.info(f"🎯 [CONSUMER] Iniciando consumer para campanha {campaign_id}")
                self.channel.start_consuming()
                
            except Exception as e:
                logger.error(f"❌ [CONSUMER] Erro no consumer: {e}")
            finally:
                # Remover da lista de consumers ativos
                if campaign_id in self.consumer_threads:
                    del self.consumer_threads[campaign_id]
        
        # Iniciar em thread separada
        thread = threading.Thread(target=start_consuming, daemon=True)
        thread.start()
        
        self.consumer_threads[campaign_id] = thread
        logger.info(f"🚀 [CONSUMER] Thread iniciada para campanha {campaign_id}")
    
    def _process_message(self, message_data: Dict[str, Any]) -> bool:
        """Processa uma mensagem individual - USA INSTÂNCIA PRÉ-SELECIONADA COM DELAY"""
        try:
            campaign_id = message_data['campaign_id']
            contact_id = message_data['contact_id']
            campaign_contact_id = message_data['campaign_contact_id']
            message_content = message_data['message_content']
            contact_phone = message_data.get('contact_phone')
            scheduled_delay = message_data.get('scheduled_delay_seconds', 0)
            
            # Buscar dados
            campaign = Campaign.objects.get(id=campaign_id)
            contact = CampaignContact.objects.get(id=campaign_contact_id)
            
            # ⏰ APLICAR DELAY ANTES DO PROCESSAMENTO COM CONTADOR REGRESSIVO
            if scheduled_delay > 0:
                logger.info(f"⏰ [DELAY] Aguardando {scheduled_delay}s antes de processar {contact.contact.name}")
                
                # Atualizar informações da próxima mensagem na campanha
                with transaction.atomic():
                    campaign.next_message_scheduled_at = timezone.now() + timedelta(seconds=scheduled_delay)
                    campaign.next_contact_name = contact.contact.name
                    campaign.next_contact_phone = contact.contact.phone
                    campaign.save(update_fields=['next_message_scheduled_at', 'next_contact_name', 'next_contact_phone'])
                
                # WebSocket será enviado apenas nos gatilhos específicos (sem spam)
                
                # Aplicar delay com contador regressivo
                for remaining_seconds in range(scheduled_delay, 0, -1):
                    # Verificar se campanha ainda está ativa a cada segundo
                    campaign.refresh_from_db()
                    if campaign.status != 'running':
                        logger.warning(f"⚠️ [DELAY] Campanha {campaign.name} pausada durante delay - {remaining_seconds}s restantes")
                        return False
                    
                    # Log a cada 10 segundos ou nos últimos 10 segundos
                    if remaining_seconds % 10 == 0 or remaining_seconds <= 10:
                        logger.info(f"⏰ [DELAY] {remaining_seconds}s restantes para {contact.contact.name}")
                    
                    time.sleep(1)
                
                logger.info(f"✅ [DELAY] Delay concluído - processando {contact.contact.name}")
                
                # 🚀 GATILHO: Próximo disparo iniciando (frontend fará contagem)
                self._send_websocket_update(campaign, 'campaign_update', {
                    'event': 'next_message_starting',
                    'contact_name': contact.contact.name,
                    'contact_phone': contact.contact.phone
                })
            
            # Verificar se campanha ainda está ativa após delay
            campaign.refresh_from_db()
            if campaign.status != 'running':
                logger.warning(f"⚠️ [DELAY] Campanha {campaign.name} não está mais ativa após delay")
                return False
            
            # 🎯 USAR INSTÂNCIA PRÉ-SELECIONADA (rotação já calculada)
            instance = self._get_pre_selected_instance(message_data)
            if not instance:
                logger.error(f"❌ [PROCESSING] Instância pré-selecionada não disponível para campanha {campaign.name}")
                return False
            
            # 🔒 VALIDAÇÕES CRÍTICAS DE SEGURANÇA
            if not self._validate_message_data(campaign, contact, instance, message_data):
                logger.error(f"❌ [SECURITY] Validação de segurança falhou para campanha {campaign.name}")
                return False
            
            logger.info(f"📤 [MESSAGE] Enviando para {contact.contact.name} ({contact_phone}) via {instance.friendly_name} (delay: {scheduled_delay}s)")
            logger.info(f"🔒 [SECURITY] Tenant: {campaign.tenant.name} | Instância: {instance.tenant.name}")
            
            # Enviar mensagem via API com retry
            success = self._send_whatsapp_message_with_retry(instance, contact_phone, message_content, campaign)
            
            if success:
                # Atualizar status
                with transaction.atomic():
                    contact.status = 'sent'
                    contact.sent_at = timezone.now()
                    contact.save()
                    
                    campaign.messages_sent += 1
                    
                    # Atualizar informações do ÚLTIMO disparo
                    campaign.last_contact_name = contact.contact.name
                    campaign.last_contact_phone = contact.contact.phone
                    campaign.last_message_sent_at = timezone.now()
                    
                    # Atualizar informações da próxima mensagem
                    next_contact = CampaignContact.objects.filter(
                        campaign=campaign,
                        status__in=['pending', 'sending']
                    ).select_related('contact').first()
                    
                    if next_contact:
                        campaign.next_contact_name = next_contact.contact.name
                        campaign.next_contact_phone = next_contact.contact.phone
                        # Calcular próximo delay
                        next_delay = random.randint(campaign.interval_min, campaign.interval_max)
                        campaign.next_message_scheduled_at = timezone.now() + timedelta(seconds=next_delay)
                    else:
                        # Nenhum contato pendente - campanha concluída
                        campaign.next_contact_name = None
                        campaign.next_contact_phone = None
                        campaign.next_message_scheduled_at = None
                        campaign.status = 'completed'
                        campaign.completed_at = timezone.now()
                    
                    campaign.save(update_fields=['messages_sent', 'last_contact_name', 'last_contact_phone', 'last_message_sent_at', 'next_contact_name', 'next_contact_phone', 'next_message_scheduled_at', 'status', 'completed_at'])
                
                # WebSocket será enviado apenas nos gatilhos específicos (sem spam)
                
                logger.info(f"✅ [MESSAGE] Mensagem enviada com sucesso via {instance.friendly_name}")
                
                # 🚀 GATILHO: Mensagem enviada - frontend atualiza e faz nova contagem
                self._send_websocket_update(campaign, 'campaign_update', {
                    'event': 'message_sent',
                    'contact_name': contact.contact.name,
                    'contact_phone': contact.contact.phone,
                    'instance_name': instance.friendly_name
                })
                
                return True
            else:
                # Marcar como falha (após 3 tentativas)
                with transaction.atomic():
                    contact.status = 'failed'
                    contact.save()
                    
                    campaign.messages_failed += 1
                    campaign.save(update_fields=['messages_failed'])
                
                logger.error(f"❌ [MESSAGE] Falha ao enviar mensagem após 3 tentativas via {instance.friendly_name}")
                
                # 🚀 GATILHO: Falha no envio
                self._send_websocket_update(campaign, 'campaign_update', {
                    'event': 'message_failed',
                    'contact_name': contact.contact.name,
                    'contact_phone': contact.contact.phone,
                    'instance_name': instance.friendly_name
                })
                
                return False
                
        except Exception as e:
            logger.error(f"❌ [MESSAGE] Erro ao processar mensagem: {e}")
            return False
    
    def _get_pre_selected_instance(self, message_data: Dict[str, Any]):
        """Busca instância pré-selecionada baseada na rotação calculada"""
        try:
            logger.info(f"🔍 [INSTANCE] Buscando instância pré-selecionada...")
            logger.info(f"🔍 [INSTANCE] message_data keys: {list(message_data.keys())}")
            
            campaign_settings = message_data.get('campaign_settings', {})
            logger.info(f"🔍 [INSTANCE] campaign_settings keys: {list(campaign_settings.keys())}")
            
            selected_instance_id = campaign_settings.get('selected_instance_id')
            logger.info(f"🔍 [INSTANCE] selected_instance_id: {selected_instance_id}")
            
            if not selected_instance_id:
                logger.error("❌ [INSTANCE] selected_instance_id não encontrado na mensagem")
                logger.error(f"❌ [INSTANCE] campaign_settings completo: {campaign_settings}")
                return None
            
            # Buscar instância específica
            instance = WhatsAppInstance.objects.get(
                id=selected_instance_id,
                is_active=True
            )
            
            logger.info(f"🎯 [INSTANCE] Usando instância pré-selecionada: {instance.friendly_name}")
            return instance
            
        except WhatsAppInstance.DoesNotExist:
            logger.error(f"❌ [INSTANCE] Instância {selected_instance_id} não encontrada ou inativa")
            # Fallback: tentar selecionar uma instância disponível
            return self._select_instance_fallback(message_data.get('campaign_settings', {}))
        except Exception as e:
            logger.error(f"❌ [INSTANCE] Erro ao buscar instância pré-selecionada: {e}")
            return None
    
    def _select_instance_fallback(self, campaign_settings: Dict[str, Any]):
        """Fallback: seleciona primeira instância disponível"""
        try:
            selected_instances = campaign_settings.get('selected_instances', [])
            if not selected_instances:
                return None
            
            # Tentar primeira instância disponível
            for instance_id in selected_instances:
                try:
                    instance = WhatsAppInstance.objects.get(
                        id=instance_id,
                        is_active=True
                    )
                    logger.info(f"🔄 [FALLBACK] Usando instância alternativa: {instance.friendly_name}")
                    return instance
                except WhatsAppInstance.DoesNotExist:
                    continue
            
            logger.error("❌ [FALLBACK] Nenhuma instância disponível encontrada")
            return None
            
        except Exception as e:
            logger.error(f"❌ [FALLBACK] Erro no fallback de instância: {e}")
            return None
    
    def _schedule_next_message(self, campaign: Campaign):
        """Agenda próxima mensagem respeitando intervalos da campanha"""
        try:
            # Buscar próximo contato pendente
            next_contact = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).select_related('contact').first()
            
            if not next_contact:
                logger.info(f"🏁 [CAMPAIGN] Campanha {campaign.name} concluída - sem mais contatos")
                # Marcar campanha como concluída
                campaign.status = 'completed'
                campaign.completed_at = timezone.now()
                campaign.save(update_fields=['status', 'completed_at'])
                return
            
            # Calcular delay baseado nos intervalos da campanha
            import random
            delay_seconds = random.randint(campaign.interval_min, campaign.interval_max)
            
            logger.info(f"⏰ [SCHEDULE] Próxima mensagem em {delay_seconds}s para {next_contact.contact.name}")
            
            # Agendar próxima mensagem com delay
            self._schedule_message_with_delay(campaign, next_contact, delay_seconds)
            
        except Exception as e:
            logger.error(f"❌ [SCHEDULE] Erro ao agendar próxima mensagem: {e}")
            # 🔄 RETRY: Tentar agendar novamente em 30 segundos
            self._schedule_retry_next_message(campaign, 30, 1)
    
    def _schedule_message_with_delay(self, campaign: Campaign, contact: CampaignContact, delay_seconds: int):
        """Agenda mensagem com delay específico"""
        try:
            import threading
            import time
            
            def delayed_message():
                # Aguardar o delay
                time.sleep(delay_seconds)
                
                # Verificar se campanha ainda está ativa
                campaign.refresh_from_db()
                if campaign.status != 'running':
                    logger.info(f"⏹️ [SCHEDULE] Campanha {campaign.name} não está mais ativa - cancelando agendamento")
                    return
                
                # Criar próxima mensagem
                message = {
                    'campaign_id': str(campaign.id),
                    'contact_id': str(contact.contact.id),
                    'campaign_contact_id': str(contact.id),
                    'instance_id': 'SELECT_AT_PROCESSING',
                    'message_content': self._get_message_content(campaign),
                    'created_at': timezone.now().isoformat(),
                    'campaign_interval_min': campaign.interval_min,
                    'campaign_interval_max': campaign.interval_max,
                    'campaign_rotation_mode': campaign.rotation_mode
                }
                
                # Verificar conexão antes de publicar
                self._check_connection()
                
                # Publicar mensagem agendada
                queue_name = f"campaign.{campaign.id}.messages"
                self.channel.basic_publish(
                    exchange='campaigns',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        timestamp=int(time.time())
                    )
                )
                
                logger.info(f"📤 [SCHEDULE] Mensagem agendada publicada para {contact.contact.name}")
            
            # Executar em thread separada
            thread = threading.Thread(target=delayed_message, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"❌ [SCHEDULE] Erro ao agendar mensagem com delay: {e}")
    
    def _schedule_retry_next_message(self, campaign: Campaign, retry_delay: int, attempt: int = 1):
        """Retry para agendar próxima mensagem em caso de erro"""
        try:
            import threading
            import time
            
            def retry_schedule():
                logger.info(f"🔄 [RETRY] Tentativa {attempt} - agendando em {retry_delay}s para campanha {campaign.name}")
                time.sleep(retry_delay)
                
                # Verificar se campanha ainda está ativa
                campaign.refresh_from_db()
                if campaign.status != 'running':
                    logger.info(f"⏹️ [RETRY] Campanha {campaign.name} não está mais ativa - cancelando retry")
                    return
                
                # Tentar agendar novamente
                try:
                    self._schedule_next_message(campaign)
                    logger.info(f"✅ [RETRY] Próxima mensagem agendada com sucesso após retry")
                except Exception as retry_error:
                    logger.error(f"❌ [RETRY] Falha no retry: {retry_error}")
                    # 🔄 RETRY LIMITADO - máximo 3 tentativas
                    if attempt < 3:
                        next_delay = retry_delay * 2  # 30s, 60s, 120s
                        logger.info(f"🔄 [RETRY] Tentativa {attempt + 1}/3 em {next_delay}s")
                        self._schedule_retry_next_message(campaign, next_delay, attempt + 1)
                    else:
                        logger.error(f"❌ [RETRY] Máximo de 3 tentativas atingido para campanha {campaign.name} - PARANDO RETRY")
                        # Marcar campanha como pausada por erro
                        campaign.status = 'paused'
                        campaign.save(update_fields=['status'])
                        CampaignLog.log_error(campaign, f"Campanha pausada após 3 tentativas de retry falharem")
            
            # Executar retry em thread separada
            thread = threading.Thread(target=retry_schedule, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"❌ [RETRY] Erro no sistema de retry: {e}")
    
    def _validate_message_data(self, campaign: Campaign, contact: CampaignContact, instance: WhatsAppInstance, message_data: Dict) -> bool:
        """Validações críticas de segurança antes do envio"""
        try:
            # 1. Verificar se a instância pertence ao mesmo tenant da campanha
            if campaign.tenant != instance.tenant:
                logger.error(f"❌ [SECURITY] VIOLAÇÃO: Instância {instance.friendly_name} não pertence ao tenant {campaign.tenant.name}")
                return False
            
            # 2. Verificar se o contato pertence à campanha
            if contact.campaign != campaign:
                logger.error(f"❌ [SECURITY] VIOLAÇÃO: Contato {contact.contact.name} não pertence à campanha {campaign.name}")
                return False
            
            # 3. Verificar se o contato pertence ao mesmo tenant
            if contact.contact.tenant != campaign.tenant:
                logger.error(f"❌ [SECURITY] VIOLAÇÃO: Contato {contact.contact.name} não pertence ao tenant {campaign.tenant.name}")
                return False
            
            # 4. Verificar se a instância está ativa
            if not instance.is_active:
                logger.error(f"❌ [SECURITY] Instância {instance.friendly_name} não está ativa")
                return False
            
            # 5. Verificar se o telefone é válido
            if not contact.contact.phone or len(contact.contact.phone) < 10:
                logger.error(f"❌ [SECURITY] Telefone inválido: {contact.contact.phone}")
                return False
            
            # 6. Verificar se a mensagem não está vazia
            if not message_data.get('message_content') or len(message_data.get('message_content', '').strip()) == 0:
                logger.error(f"❌ [SECURITY] Mensagem vazia ou inválida")
                return False
            
            # 7. Verificar IDs da mensagem
            expected_contact_id = str(contact.contact.id)
            if message_data.get('contact_id') != expected_contact_id:
                logger.error(f"❌ [SECURITY] ID do contato não confere: esperado {expected_contact_id}, recebido {message_data.get('contact_id')}")
                return False
            
            expected_instance_id = str(instance.id)
            # Verificar se a instância está na lista de instâncias selecionadas da campanha
            campaign_settings = message_data.get('campaign_settings', {})
            selected_instance_id = campaign_settings.get('selected_instance_id')
            
            if selected_instance_id != expected_instance_id:
                logger.error(f"❌ [SECURITY] ID da instância não confere: esperado {expected_instance_id}, recebido {selected_instance_id}")
                return False
            
            # Verificar se a instância está na lista de instâncias selecionadas
            selected_instances = campaign_settings.get('selected_instances', [])
            if expected_instance_id not in selected_instances:
                logger.error(f"❌ [SECURITY] Instância {expected_instance_id} não está na lista de instâncias selecionadas: {selected_instances}")
                return False
            
            logger.info(f"✅ [SECURITY] Todas as validações passaram para {contact.contact.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [SECURITY] Erro nas validações: {e}")
            return False

    def _send_whatsapp_message_with_retry(self, instance: WhatsAppInstance, phone: str, message: str, campaign: Campaign) -> bool:
        """Envia mensagem via API do WhatsApp com 3 tentativas"""
        import time
        
        for attempt in range(1, 4):  # 3 tentativas
            try:
                url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
                headers = {
                    'apikey': instance.api_key,
                    'Content-Type': 'application/json'
                }
                payload = {
                    'number': phone,
                    'text': message
                }
                
                # Log detalhado do envio
                logger.info(f"📤 [API] Tentativa {attempt}/3 - Enviando via {instance.friendly_name} para {phone}")
                logger.info(f"🔗 [API] URL: {url}")
                logger.info(f"📝 [API] Conteúdo: {message[:100]}...")
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                logger.info(f"✅ [API] Mensagem enviada com sucesso na tentativa {attempt}")
                return True
                
            except Exception as e:
                logger.error(f"❌ [API] Tentativa {attempt}/3 falhou: {e}")
                
                if attempt < 3:
                    # Delay entre tentativas: 2s, 4s
                    delay = 2 ** attempt
                    logger.info(f"⏰ [RETRY] Aguardando {delay}s antes da próxima tentativa")
                    time.sleep(delay)
                else:
                    logger.error(f"❌ [API] Todas as 3 tentativas falharam para {phone}")
                    return False
        
        return False

    def _send_whatsapp_message(self, instance: WhatsAppInstance, phone: str, message: str) -> bool:
        """Envia mensagem via API do WhatsApp (método simples para compatibilidade)"""
        try:
            url = f"{instance.api_url}/message/sendText/{instance.instance_name}"
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'number': phone,
                'text': message
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [WHATSAPP] Erro ao enviar mensagem: {e}")
            return False
    
    def _select_instance(self, campaign: Campaign) -> Optional[WhatsAppInstance]:
        """Seleciona instância disponível - APENAS INSTÂNCIAS SELECIONADAS NA CAMPANHA"""
        try:
            # 🎯 USAR APENAS INSTÂNCIAS SELECIONADAS NA CAMPANHA (como o Celery fazia)
            available_instances = campaign.instances.filter(
                is_active=True,
                health_score__gte=campaign.pause_on_health_below
            )
            
            if not available_instances.exists():
                logger.warning(f"⚠️ [CONSUMER] Nenhuma instância disponível para tenant {campaign.tenant.name}")
                return None
            
            logger.info(f"🔒 [SEGURANÇA] Selecionando instância para tenant: {campaign.tenant.name}")
            
            # Implementar lógica baseada no modo de rotação da campanha
            if campaign.rotation_mode == 'round_robin':
                # Round robin baseado em contador sequencial
                if not hasattr(self, '_round_robin_counter'):
                    self._round_robin_counter = 0
                
                self._round_robin_counter += 1
                index = self._round_robin_counter % available_instances.count()
                instance = available_instances[index]
                logger.info(f"🔄 [ROUND_ROBIN] Selecionada instância: {instance.friendly_name} (index: {index})")
                return instance
            elif campaign.rotation_mode == 'intelligent':
                # Selecionar instância com melhor health_score
                instance = available_instances.order_by('-health_score').first()
                logger.info(f"🧠 [INTELLIGENT] Selecionada instância: {instance.friendly_name} (health: {instance.health_score})")
                return instance
            else:
                # Fallback para primeira instância
                instance = available_instances.first()
                logger.info(f"📱 [DEFAULT] Selecionada instância: {instance.friendly_name}")
                return instance
            
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao selecionar instância: {e}")
            return None
    
    def _get_message_content(self, campaign: Campaign, contact_position: int = 0) -> str:
        """Obtém conteúdo da mensagem com rotação baseada na posição do contato"""
        try:
            # Buscar mensagens da campanha
            from .models import CampaignMessage
            messages = CampaignMessage.objects.filter(campaign=campaign).order_by('order', 'created_at')
            
            if messages.exists():
                # Implementar rotação de mensagens baseada na posição do contato
                message_count = messages.count()
                message_index = contact_position % message_count
                selected_message = messages[message_index]
                
                logger.info(f"🔄 [MESSAGE_ROTATION] Contato posição {contact_position}: usando mensagem {message_index + 1}/{message_count} (ID: {selected_message.id})")
                
                return selected_message.content
            else:
                logger.warning(f"⚠️ [CONSUMER] Nenhuma mensagem encontrada para campanha {campaign.name}")
                return f"Mensagem da campanha {campaign.name}"
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao obter conteúdo: {e}")
            return f"Mensagem da campanha {campaign.name}"
    
    def _send_websocket_update(self, campaign, event_type, extra_data=None):
        """Envia atualização WebSocket apenas em eventos específicos"""
        try:
            logger.info(f"🔧 [WEBSOCKET] Iniciando envio de {event_type} para campanha {campaign.name}")
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            async def send_update():
                logger.info(f"🔧 [WEBSOCKET] Dentro da função async para {event_type}")
                # Dados básicos da campanha
                campaign_data = {
                    'type': event_type,
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'status': campaign.status,
                    'messages_sent': campaign.messages_sent,
                    'messages_delivered': campaign.messages_delivered,
                    'messages_read': campaign.messages_read,
                    'messages_failed': campaign.messages_failed,
                    'total_contacts': campaign.total_contacts,
                    'progress_percentage': (campaign.messages_sent / campaign.total_contacts * 100) if campaign.total_contacts > 0 else 0,
                    'last_message_sent_at': campaign.last_message_sent_at.isoformat() if campaign.last_message_sent_at else None,
                    'next_message_scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                    'next_contact_name': campaign.next_contact_name,
                    'next_contact_phone': campaign.next_contact_phone,
                    'last_contact_name': campaign.last_contact_name,
                    'last_contact_phone': campaign.last_contact_phone,
                    'updated_at': campaign.updated_at.isoformat()
                }
                
                # Adicionar dados extras se fornecidos
                if extra_data:
                    campaign_data.update(extra_data)
                
                # Enviar via WebSocket
                channel_layer = get_channel_layer()
                if channel_layer:
                    await channel_layer.group_send(
                        f"tenant_{campaign.tenant.id}",
                        {
                            "type": "broadcast_notification",
                            "payload": campaign_data
                        }
                    )
                    logger.info(f"📡 [WEBSOCKET] {event_type} enviado para campanha {campaign.name}")
            
            # Usar async_to_sync para execução mais confiável
            async_to_sync(send_update)()
                
        except Exception as e:
            logger.error(f"❌ [WEBSOCKET] Erro ao enviar {event_type}: {e}")

    async def _send_campaign_update_websocket(self, campaign):
        """Envia atualização da campanha via WebSocket"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            # Calcular tempo restante
            time_remaining = None
            if campaign.next_message_scheduled_at and campaign.status == 'running':
                from django.utils import timezone
                now = timezone.now()
                if campaign.next_message_scheduled_at > now:
                    delta = campaign.next_message_scheduled_at - now
                    time_remaining = int(delta.total_seconds())
                else:
                    time_remaining = 0
            
            # Dados da campanha para WebSocket
            campaign_data = {
                'type': 'campaign_update',
                'campaign_id': str(campaign.id),
                'status': campaign.status,
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_read': campaign.messages_read,
                'messages_failed': campaign.messages_failed,
                'total_contacts': campaign.total_contacts,
                'progress_percentage': (campaign.messages_sent / campaign.total_contacts * 100) if campaign.total_contacts > 0 else 0,
                'last_message': {
                    'contact_name': campaign.last_contact_name,
                    'contact_phone': campaign.last_contact_phone,
                    'sent_at': campaign.last_message_sent_at.isoformat() if campaign.last_message_sent_at else None
                },
                'next_message': {
                    'contact_name': campaign.next_contact_name,
                    'contact_phone': campaign.next_contact_phone,
                    'scheduled_at': campaign.next_message_scheduled_at.isoformat() if campaign.next_message_scheduled_at else None,
                    'time_remaining_seconds': time_remaining
                },
                'updated_at': campaign.updated_at.isoformat()
            }
            
            # Enviar via WebSocket
            channel_layer = get_channel_layer()
            if channel_layer:
                await channel_layer.group_send(
                    f"tenant_{campaign.tenant.id}",
                    {
                        "type": "broadcast_notification",
                        "payload": campaign_data
                    }
                )
                
                logger.info(f"📡 [WEBSOCKET] Atualização enviada para campanha {campaign.name}")
                
        except Exception as e:
            logger.error(f"❌ [WEBSOCKET] Erro ao enviar atualização: {e}")
    
    def _handle_failed_message(self, message_data: Dict[str, Any]):
        """Trata mensagem que falhou"""
        try:
            # Adicionar contador de retry
            message_data['retry_count'] = message_data.get('retry_count', 0) + 1
            message_data['max_retries'] = 3
            
            if message_data['retry_count'] <= message_data['max_retries']:
                # Reenviar para retry
                self.channel.basic_publish(
                    exchange='campaigns',
                    routing_key='campaign.retry',
                    body=json.dumps(message_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        timestamp=int(time.time())
                    )
                )
                logger.info(f"🔄 [RETRY] Reenviando mensagem (tentativa {message_data['retry_count']})")
            else:
                # Enviar para DLQ
                self.channel.basic_publish(
                    exchange='campaigns',
                    routing_key='campaign.dlq',
                    body=json.dumps(message_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        timestamp=int(time.time())
                    )
                )
                logger.error(f"💀 [DLQ] Mensagem enviada para dead letter queue")
                
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao tratar mensagem falhada: {e}")
    
    def pause_campaign(self, campaign_id: str):
        """Pausa uma campanha"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.status = 'paused'
            campaign.save(update_fields=['status'])
            
            CampaignLog.log_campaign_paused(campaign)
            logger.info(f"⏸️ [CONSUMER] Campanha {campaign.name} pausada")
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [CONSUMER] Campanha {campaign_id} não encontrada")
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao pausar campanha: {e}")
    
    def resume_campaign(self, campaign_id: str):
        """Resume uma campanha"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.status = 'running'
            campaign.save(update_fields=['status'])
            
            CampaignLog.log_campaign_resumed(campaign)
            logger.info(f"▶️ [CONSUMER] Campanha {campaign.name} resumida")
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [CONSUMER] Campanha {campaign_id} não encontrada")
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao resumir campanha: {e}")
    
    def stop_campaign(self, campaign_id: str):
        """Para uma campanha"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.status = 'completed'
            campaign.save(update_fields=['status'])
            
            # Parar consumer se ativo
            if campaign_id in self.consumer_threads:
                del self.consumer_threads[campaign_id]
            
            CampaignLog.log_campaign_completed(campaign)
            logger.info(f"🛑 [CONSUMER] Campanha {campaign.name} parada")
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [CONSUMER] Campanha {campaign_id} não encontrada")
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao parar campanha: {e}")
    
    def get_active_campaigns(self) -> list:
        """Lista campanhas ativas"""
        return list(self.consumer_threads.keys())
    
    def force_start(self):
        """Força o início do consumer (para uso via admin)"""
        try:
            if not self.is_running:
                self.start(auto_start_campaigns=True)
                return True, "Consumer iniciado com sucesso"
            else:
                return False, "Consumer já está rodando"
        except Exception as e:
            return False, f"Erro ao iniciar consumer: {str(e)}"
    
    def force_stop(self):
        """Força a parada do consumer (para uso via admin)"""
        try:
            if self.is_running:
                self.stop()
                return True, "Consumer parado com sucesso"
            else:
                return False, "Consumer já está parado"
        except Exception as e:
            return False, f"Erro ao parar consumer: {str(e)}"
    
    def force_restart(self):
        """Força o reinício do consumer (para uso via admin)"""
        try:
            if self.is_running:
                self.stop()
                time.sleep(2)  # Aguardar um pouco
            self.start(auto_start_campaigns=True)
            return True, "Consumer reiniciado com sucesso"
        except Exception as e:
            return False, f"Erro ao reiniciar consumer: {str(e)}"
    
    def get_detailed_status(self):
        """Retorna status detalhado do consumer"""
        try:
            active_campaigns = self.get_active_campaigns()
            campaign_details = []
            
            for campaign_id in active_campaigns:
                status = self.get_campaign_status(campaign_id)
                campaign_details.append({
                    'campaign_id': campaign_id,
                    'status': status.get('status', 'unknown'),
                    'is_running': status.get('is_running', False),
                    'messages_processed': status.get('messages_processed', 0),
                    'last_activity': status.get('last_activity', None),
                })
            
            return {
                'is_running': self.is_running,
                'connection_status': 'connected' if self.connection and not self.connection.is_closed else 'disconnected',
                'active_campaigns_count': len(active_campaigns),
                'active_campaigns': active_campaigns,
                'campaign_details': campaign_details,
                'monitor_running': self.monitor_thread and self.monitor_thread.is_alive() if self.monitor_thread else False,
            }
        except Exception as e:
            return {
                'is_running': False,
                'connection_status': 'error',
                'error': str(e),
                'active_campaigns_count': 0,
                'active_campaigns': [],
                'campaign_details': [],
                'monitor_running': False,
            }
    
    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Retorna status de uma campanha"""
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            is_active = campaign_id in self.consumer_threads
            
            return {
                'campaign_id': campaign_id,
                'campaign_name': campaign.name,
                'status': campaign.status,
                'is_consumer_active': is_active,
                'messages_sent': campaign.messages_sent,
                'messages_delivered': campaign.messages_delivered,
                'messages_failed': campaign.messages_failed
            }
            
        except Campaign.DoesNotExist:
            return None
    
    def start_health_monitor(self):
        """Inicia monitor de saúde"""
        def health_monitor():
            while self.running:
                try:
                    self._perform_health_check()
                    time.sleep(30)  # Verificar a cada 30 segundos
                except Exception as e:
                    logger.error(f"❌ [HEALTH] Erro no monitor: {e}")
                    time.sleep(10)
        
        thread = threading.Thread(target=health_monitor, daemon=True)
        thread.start()
        logger.info("🔍 [HEALTH] Monitor de saúde iniciado")
    
    def _perform_health_check(self):
        """Executa verificação de saúde"""
        try:
            # Verificar campanhas que deveriam estar rodando
            running_campaigns = Campaign.objects.filter(status='running')
            
            for campaign in running_campaigns:
                campaign_id = str(campaign.id)
                
                if campaign_id not in self.consumer_threads:
                    logger.warning(f"⚠️ [HEALTH] Campanha {campaign.name} deveria estar rodando mas consumer não está ativo")
                    
                    # Tentar reiniciar
                    self.start_campaign(campaign_id)
            
            # Verificar contatos pendentes
            for campaign in running_campaigns:
                pending_count = CampaignContact.objects.filter(
                    campaign=campaign,
                    status__in=['pending', 'sending']
                ).count()
                
                if pending_count == 0:
                    logger.info(f"🎯 [HEALTH] Campanha {campaign.name} completada")
                    campaign.complete()
                
        except Exception as e:
            logger.error(f"❌ [HEALTH] Erro na verificação: {e}")
    
    def start(self, auto_start_campaigns=False):
        """Inicia o consumer"""
        self.running = True
        self.start_health_monitor()
        logger.info("🚀 [CONSUMER] RabbitMQ Consumer iniciado")
        
        # Iniciar campanhas ativas automaticamente se solicitado
        if auto_start_campaigns:
            self._auto_start_active_campaigns()
    
    def _auto_start_active_campaigns(self):
        """Inicia automaticamente campanhas que estão em execução"""
        try:
            from .models import Campaign
            
            # Buscar campanhas em execução
            running_campaigns = Campaign.objects.filter(status='running')
            
            for campaign in running_campaigns:
                campaign_id = str(campaign.id)
                if campaign_id not in self.consumer_threads:
                    logger.info(f"🚀 [AUTO-START] Iniciando campanha {campaign.name}")
                    self.start_campaign(campaign_id)
                    
            # 🔄 RECOVERY: Verificar campanhas travadas a cada 5 minutos
            self._start_campaign_recovery_monitor()
                    
        except Exception as e:
            logger.error(f"❌ [AUTO-START] Erro ao iniciar campanhas: {e}")
    
    def _start_campaign_recovery_monitor(self):
        """Monitor para recuperar campanhas travadas"""
        import threading
        import time
        
        def recovery_monitor():
            while self.running:
                try:
                    time.sleep(60)  # Verificar a cada 1 minuto (mais frequente)
                    
                    from .models import Campaign
                    running_campaigns = Campaign.objects.filter(status='running')
                    
                    for campaign in running_campaigns:
                        campaign_id = str(campaign.id)
                        
                        # Se campanha está rodando mas sem consumer ativo
                        if campaign_id not in self.consumer_threads:
                            logger.warning(f"🔄 [RECOVERY] Campanha {campaign.name} sem consumer - reiniciando")
                            self.start_campaign(campaign_id)
                        
                        # Verificar se tem contatos pendentes mas sem processamento
                        pending_contacts = CampaignContact.objects.filter(
                            campaign=campaign,
                            status__in=['pending', 'sending']
                        ).count()
                        
                        if pending_contacts > 0:
                            # Verificar se consumer está ativo mas não processando
                            if campaign_id in self.consumer_threads:
                                thread = self.consumer_threads[campaign_id]
                                if not thread.is_alive():
                                    logger.warning(f"🔄 [RECOVERY] Consumer morto para {campaign.name} - reiniciando")
                                    del self.consumer_threads[campaign_id]
                                    self.start_campaign(campaign_id)
                                    
                except Exception as e:
                    logger.error(f"❌ [RECOVERY] Erro no monitor de recuperação: {e}")
                    time.sleep(60)  # Aguardar 1 minuto antes de tentar novamente
        
        # Iniciar monitor em thread separada
        thread = threading.Thread(target=recovery_monitor, daemon=True)
        thread.start()
        logger.info("🔄 [RECOVERY] Monitor de recuperação de campanhas iniciado")
    
    def stop(self):
        """Para o consumer"""
        self.running = False
        
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        
        logger.info("🛑 [CONSUMER] RabbitMQ Consumer parado")


# Instância global do consumer - inicializada apenas quando necessário
rabbitmq_consumer = None

def get_rabbitmq_consumer():
    """Obtém instância do consumer, criando se necessário"""
    global rabbitmq_consumer
    if rabbitmq_consumer is None:
        try:
            rabbitmq_consumer = RabbitMQConsumer()
        except Exception as e:
            print(f"⚠️ [RABBITMQ] Consumer não pode ser inicializado: {e}")
            rabbitmq_consumer = None
    return rabbitmq_consumer
