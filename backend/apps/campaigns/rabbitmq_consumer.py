"""
Consumer RabbitMQ Puro - Sistema de Campanhas
Implementa processamento robusto sem Celery
"""
import json
import time
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
        """Estabelece conexão com RabbitMQ"""
        try:
            rabbitmq_url = getattr(settings, 'RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
            
            self.connection = pika.BlockingConnection(
                pika.URLParameters(rabbitmq_url)
            )
            self.channel = self.connection.channel()
            
            # Configurar exchanges e filas
            self._setup_queues()
            
            logger.info("✅ [RABBITMQ] Conectado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [RABBITMQ] Erro na conexão: {e}")
            raise
    
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
            # Verificar se canal está aberto
            if not self.channel or self.channel.is_closed:
                logger.warning("⚠️ [CONSUMER] Canal fechado, reconectando...")
                self._connect()
            
            campaign = Campaign.objects.get(id=campaign_id)
            
            if campaign.status not in ['draft', 'running']:
                logger.warning(f"⚠️ [CONSUMER] Campanha {campaign.name} status inválido: {campaign.status}")
                return False
            
            # Verificar se tem contatos
            pending_contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).count()
            
            total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
            logger.info(f"🔍 [CONSUMER] Campanha {campaign.name}: {pending_contacts} pendentes de {total_contacts} total")
            
            if pending_contacts == 0:
                logger.warning(f"⚠️ [CONSUMER] Campanha {campaign.name} não possui contatos pendentes")
                return False
            
            # Atualizar status
            campaign.status = 'running'
            campaign.save(update_fields=['status'])
            
            # Log de início
            CampaignLog.log_campaign_started(campaign)
            
            # Criar fila específica da campanha
            queue_name = f"campaign.{campaign_id}.messages"
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.queue_bind(
                exchange='campaigns',
                queue=queue_name,
                routing_key=queue_name
            )
            
            # Adicionar mensagens à fila
            self._populate_campaign_queue(campaign)
            
            # Iniciar consumer para esta campanha
            self._start_campaign_consumer(campaign_id)
            
            logger.info(f"🚀 [CONSUMER] Campanha {campaign.name} iniciada")
            return True
            
        except Campaign.DoesNotExist:
            logger.error(f"❌ [CONSUMER] Campanha {campaign_id} não encontrada")
            return False
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao iniciar campanha: {e}")
            return False
    
    def _populate_campaign_queue(self, campaign: Campaign):
        """Popula fila com mensagens da campanha"""
        try:
            contacts = CampaignContact.objects.filter(
                campaign=campaign,
                status__in=['pending', 'sending']
            ).select_related('contact')
            
            queue_name = f"campaign.{campaign.id}.messages"
            
            for contact in contacts:
                # Selecionar instância
                instance = self._select_instance(campaign)
                if not instance:
                    logger.warning(f"⚠️ [CONSUMER] Nenhuma instância disponível para {contact.contact.name}")
                    continue
                
                # Criar mensagem
                message = {
                    'campaign_id': str(campaign.id),
                    'contact_id': str(contact.contact.id),
                    'campaign_contact_id': str(contact.id),
                    'instance_id': str(instance.id),
                    'message_content': self._get_message_content(campaign),
                    'created_at': timezone.now().isoformat()
                }
                
                # Verificar se canal está aberto antes de publicar
                if not self.channel or self.channel.is_closed:
                    logger.warning("⚠️ [CONSUMER] Canal fechado, reconectando...")
                    self._connect()
                
                # Publicar na fila
                self.channel.basic_publish(
                    exchange='campaigns',
                    routing_key=queue_name,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistir mensagem
                        timestamp=int(time.time())
                    )
                )
            
            logger.info(f"📤 [CONSUMER] {contacts.count()} mensagens adicionadas à fila")
            
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
                
                if success:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    # Reenviar para retry
                    self._handle_failed_message(message_data)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    
            except Exception as e:
                logger.error(f"❌ [CONSUMER] Erro ao processar mensagem: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
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
        """Processa uma mensagem individual"""
        try:
            campaign_id = message_data['campaign_id']
            contact_id = message_data['contact_id']
            campaign_contact_id = message_data['campaign_contact_id']
            instance_id = message_data['instance_id']
            message_content = message_data['message_content']
            
            # Buscar dados
            campaign = Campaign.objects.get(id=campaign_id)
            contact = CampaignContact.objects.get(id=campaign_contact_id)
            instance = WhatsAppInstance.objects.get(id=instance_id)
            
            logger.info(f"📤 [MESSAGE] Enviando para {contact.contact.name} via {instance.friendly_name}")
            
            # Enviar mensagem via API
            success = self._send_whatsapp_message(instance, contact.contact.phone, message_content)
            
            if success:
                # Atualizar status
                with transaction.atomic():
                    contact.status = 'sent'
                    contact.sent_at = timezone.now()
                    contact.save()
                    
                    campaign.messages_sent += 1
                    campaign.save(update_fields=['messages_sent'])
                
                logger.info(f"✅ [MESSAGE] Mensagem enviada com sucesso")
                return True
            else:
                # Marcar como falha
                with transaction.atomic():
                    contact.status = 'failed'
                    contact.save()
                    
                    campaign.messages_failed += 1
                    campaign.save(update_fields=['messages_failed'])
                
                logger.error(f"❌ [MESSAGE] Falha ao enviar mensagem")
                return False
                
        except Exception as e:
            logger.error(f"❌ [MESSAGE] Erro ao processar mensagem: {e}")
            return False
    
    def _send_whatsapp_message(self, instance: WhatsAppInstance, phone: str, message: str) -> bool:
        """Envia mensagem via API do WhatsApp"""
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
        """Seleciona instância disponível"""
        try:
            available_instances = WhatsAppInstance.objects.filter(
                is_active=True,
                health_score__gte=campaign.pause_on_health_below
            )
            
            if not available_instances.exists():
                logger.warning("⚠️ [CONSUMER] Nenhuma instância disponível")
                return None
            
            # Implementar lógica baseada no modo de rotação da campanha
            if campaign.rotation_mode == 'round_robin':
                # Round robin baseado em contador sequencial
                if not hasattr(self, '_round_robin_counter'):
                    self._round_robin_counter = 0
                
                self._round_robin_counter += 1
                index = self._round_robin_counter % available_instances.count()
                instance = available_instances[index]
                logger.info(f"🔄 [ROUND_ROBIN] Selecionada instância: {instance.name} (index: {index})")
                return instance
            elif campaign.rotation_mode == 'intelligent':
                # Selecionar instância com melhor health_score
                instance = available_instances.order_by('-health_score').first()
                logger.info(f"🧠 [INTELLIGENT] Selecionada instância: {instance.name} (health: {instance.health_score})")
                return instance
            else:
                # Fallback para primeira instância
                instance = available_instances.first()
                logger.info(f"📱 [DEFAULT] Selecionada instância: {instance.name}")
                return instance
            
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao selecionar instância: {e}")
            return None
    
    def _get_message_content(self, campaign: Campaign) -> str:
        """Obtém conteúdo da mensagem"""
        try:
            # Buscar mensagens da campanha
            from .models import CampaignMessage
            messages = CampaignMessage.objects.filter(campaign=campaign, is_active=True)
            
            if messages.exists():
                # Retornar a primeira mensagem ativa
                return messages.first().content
            else:
                logger.warning(f"⚠️ [CONSUMER] Nenhuma mensagem encontrada para campanha {campaign.name}")
                return f"Mensagem da campanha {campaign.name}"
        except Exception as e:
            logger.error(f"❌ [CONSUMER] Erro ao obter conteúdo: {e}")
            return f"Mensagem da campanha {campaign.name}"
    
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
                    
        except Exception as e:
            logger.error(f"❌ [AUTO-START] Erro ao iniciar campanhas: {e}")
    
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
