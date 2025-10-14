"""
Engine de Campanhas - Sistema Robusto e Confiável
Implementa arquitetura baseada em filas com auto-recovery
"""
import json
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import pika
import threading
from concurrent.futures import ThreadPoolExecutor

from .models import Campaign, CampaignContact, CampaignLog
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


class CampaignStatus(Enum):
    """Status interno da campanha"""
    INITIALIZING = 'initializing'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RECOVERING = 'recovering'


@dataclass
class MessagePayload:
    """Payload para mensagens na fila"""
    campaign_id: str
    contact_id: str
    instance_id: str
    message_content: str
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = timezone.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'campaign_id': self.campaign_id,
            'contact_id': self.contact_id,
            'instance_id': self.instance_id,
            'message_content': self.message_content,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessagePayload':
        return cls(**data)


class RabbitMQManager:
    """Gerenciador de conexões RabbitMQ"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()
    
    def _connect(self):
        """Estabelece conexão com RabbitMQ"""
        try:
            # Configurações do RabbitMQ (ajustar conforme ambiente)
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
    
    def publish_message(self, queue_name: str, payload: Dict[str, Any]):
        """Publica mensagem na fila"""
        try:
            self.channel.basic_publish(
                exchange='campaigns',
                routing_key=queue_name,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistir mensagem
                    timestamp=int(time.time())
                )
            )
            logger.debug(f"📤 [RABBITMQ] Mensagem publicada em {queue_name}")
            
        except Exception as e:
            logger.error(f"❌ [RABBITMQ] Erro ao publicar: {e}")
            raise
    
    def consume_messages(self, queue_name: str, callback, auto_ack=True):
        """Consome mensagens da fila"""
        try:
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback,
                auto_ack=auto_ack
            )
            self.channel.start_consuming()
            
        except Exception as e:
            logger.error(f"❌ [RABBITMQ] Erro ao consumir: {e}")
            raise
    
    def close(self):
        """Fecha conexão"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


class CampaignEngine:
    """Engine principal de campanhas"""
    
    def __init__(self, campaign_id: str):
        self.campaign_id = campaign_id
        self.campaign = None
        self.rabbitmq = RabbitMQManager()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.status = CampaignStatus.INITIALIZING
        self.health_check_interval = 30  # segundos
        self.last_health_check = None
        self._load_campaign()
    
    def _load_campaign(self):
        """Carrega dados da campanha"""
        try:
            self.campaign = Campaign.objects.get(id=self.campaign_id)
            logger.info(f"🎯 [ENGINE] Campanha carregada: {self.campaign.name}")
        except Campaign.DoesNotExist:
            logger.error(f"❌ [ENGINE] Campanha não encontrada: {self.campaign_id}")
            raise
    
    def start(self):
        """Inicia processamento da campanha"""
        try:
            logger.info(f"🚀 [ENGINE] Iniciando campanha: {self.campaign.name}")
            
            # Atualizar status
            self.status = CampaignStatus.RUNNING
            self.campaign.status = 'running'
            self.campaign.save(update_fields=['status'])
            
            # Log de início
            CampaignLog.log_campaign_started(self.campaign)
            
            # Inicializar fila de mensagens
            self._initialize_message_queue()
            
            # Iniciar health monitor
            self._start_health_monitor()
            
            # Iniciar processamento
            self._start_processing()
            
        except Exception as e:
            logger.error(f"❌ [ENGINE] Erro ao iniciar campanha: {e}")
            self.status = CampaignStatus.FAILED
            raise
    
    def _initialize_message_queue(self):
        """Inicializa fila de mensagens para a campanha"""
        queue_name = f"campaign.{self.campaign_id}.messages"
        
        # Declarar fila específica da campanha
        self.rabbitmq.channel.queue_declare(queue=queue_name, durable=True)
        self.rabbitmq.channel.queue_bind(
            exchange='campaigns',
            queue=queue_name,
            routing_key=queue_name
        )
        
        # Adicionar mensagens à fila
        self._populate_message_queue()
        
        logger.info(f"📦 [ENGINE] Fila inicializada: {queue_name}")
    
    def _populate_message_queue(self):
        """Popula fila com mensagens pendentes"""
        contacts = CampaignContact.objects.filter(
            campaign=self.campaign,
            status__in=['pending', 'sending']
        ).select_related('contact')
        
        for contact in contacts:
            # Selecionar instância
            instance = self._select_instance()
            if not instance:
                logger.warning(f"⚠️ [ENGINE] Nenhuma instância disponível para {contact.contact.name}")
                continue
            
            # Criar payload
            payload = MessagePayload(
                campaign_id=str(self.campaign.id),
                contact_id=str(contact.contact.id),
                instance_id=str(instance.id),
                message_content=self._get_message_content()
            )
            
            # Publicar na fila
            self.rabbitmq.publish_message(
                f"campaign.{self.campaign_id}.messages",
                payload.to_dict()
            )
        
        logger.info(f"📤 [ENGINE] {contacts.count()} mensagens adicionadas à fila")
    
    def _select_instance(self) -> Optional[WhatsAppInstance]:
        """Seleciona instância disponível"""
        # Implementar lógica de seleção baseada no rotation_mode
        available_instances = WhatsAppInstance.objects.filter(
            is_active=True,
            health_score__gte=self.campaign.pause_on_health_below
        )
        
        if not available_instances.exists():
            return None
        
        # Lógica simples de round robin
        return available_instances.first()
    
    def _get_message_content(self) -> str:
        """Obtém conteúdo da mensagem"""
        # Implementar lógica de seleção de mensagem
        return "Mensagem da campanha"
    
    def _start_health_monitor(self):
        """Inicia monitor de saúde"""
        def health_monitor():
            while self.status == CampaignStatus.RUNNING:
                try:
                    self._perform_health_check()
                    time.sleep(self.health_check_interval)
                except Exception as e:
                    logger.error(f"❌ [HEALTH] Erro no monitor: {e}")
                    time.sleep(10)  # Pausa em caso de erro
        
        # Executar em thread separada
        self.executor.submit(health_monitor)
        logger.info("🔍 [ENGINE] Health monitor iniciado")
    
    def _perform_health_check(self):
        """Executa verificação de saúde"""
        try:
            # Verificar se campanha ainda está ativa
            self.campaign.refresh_from_db()
            
            if self.campaign.status != 'running':
                logger.info(f"⏸️ [HEALTH] Campanha pausada externamente")
                self.status = CampaignStatus.PAUSED
                return
            
            # Verificar progresso
            pending_count = CampaignContact.objects.filter(
                campaign=self.campaign,
                status__in=['pending', 'sending']
            ).count()
            
            if pending_count == 0:
                logger.info(f"🎯 [HEALTH] Campanha concluída")
                self.status = CampaignStatus.COMPLETED
                self.campaign.complete()
                return
            
            # Verificar instâncias
            available_instances = WhatsAppInstance.objects.filter(
                is_active=True
            ).count()
            
            if available_instances == 0:
                logger.warning(f"⚠️ [HEALTH] Nenhuma instância disponível")
                self.status = CampaignStatus.FAILED
                return
            
            self.last_health_check = timezone.now()
            logger.debug(f"✅ [HEALTH] Campanha saudável - {pending_count} pendentes")
            
        except Exception as e:
            logger.error(f"❌ [HEALTH] Erro na verificação: {e}")
            self.status = CampaignStatus.FAILED
    
    def _start_processing(self):
        """Inicia processamento de mensagens"""
        queue_name = f"campaign.{self.campaign_id}.messages"
        
        def message_callback(ch, method, properties, body):
            try:
                payload_data = json.loads(body)
                payload = MessagePayload.from_dict(payload_data)
                
                # Processar mensagem
                success = self._process_message(payload)
                
                if success:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    # Reenviar para retry ou DLQ
                    self._handle_failed_message(payload)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    
            except Exception as e:
                logger.error(f"❌ [PROCESSING] Erro ao processar mensagem: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        # Consumir mensagens
        self.rabbitmq.consume_messages(queue_name, message_callback, auto_ack=False)
    
    def _process_message(self, payload: MessagePayload) -> bool:
        """Processa uma mensagem individual"""
        try:
            # Implementar lógica de envio
            # Aqui seria a integração com a API do WhatsApp
            
            logger.info(f"📤 [MESSAGE] Enviando para contato {payload.contact_id}")
            
            # Simular envio (substituir por lógica real)
            time.sleep(1)
            
            # Atualizar status do contato
            with transaction.atomic():
                contact = CampaignContact.objects.get(
                    campaign_id=payload.campaign_id,
                    contact_id=payload.contact_id
                )
                contact.status = 'sent'
                contact.sent_at = timezone.now()
                contact.save()
                
                # Atualizar contadores da campanha
                self.campaign.messages_sent += 1
                self.campaign.save(update_fields=['messages_sent'])
            
            logger.info(f"✅ [MESSAGE] Mensagem enviada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ [MESSAGE] Erro ao enviar: {e}")
            return False
    
    def _handle_failed_message(self, payload: MessagePayload):
        """Trata mensagem que falhou"""
        payload.retry_count += 1
        
        if payload.retry_count <= payload.max_retries:
            # Reenviar para retry
            self.rabbitmq.publish_message(
                'campaign.retry',
                payload.to_dict()
            )
            logger.info(f"🔄 [RETRY] Reenviando mensagem (tentativa {payload.retry_count})")
        else:
            # Enviar para DLQ
            self.rabbitmq.publish_message(
                'campaign.dlq',
                payload.to_dict()
            )
            logger.error(f"💀 [DLQ] Mensagem enviada para dead letter queue")
    
    def pause(self):
        """Pausa a campanha"""
        logger.info(f"⏸️ [ENGINE] Pausando campanha")
        self.status = CampaignStatus.PAUSED
        self.campaign.status = 'paused'
        self.campaign.save(update_fields=['status'])
        
        CampaignLog.log_campaign_paused(self.campaign)
    
    def resume(self):
        """Resume a campanha"""
        logger.info(f"▶️ [ENGINE] Resumindo campanha")
        self.status = CampaignStatus.RUNNING
        self.campaign.status = 'running'
        self.campaign.save(update_fields=['status'])
        
        CampaignLog.log_campaign_resumed(self.campaign)
    
    def stop(self):
        """Para a campanha"""
        logger.info(f"🛑 [ENGINE] Parando campanha")
        self.status = CampaignStatus.COMPLETED
        self.campaign.status = 'completed'
        self.campaign.save(update_fields=['status'])
        
        # Limpar recursos
        self.rabbitmq.close()
        self.executor.shutdown(wait=False)
        
        CampaignLog.log_campaign_completed(self.campaign)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual da campanha"""
        return {
            'campaign_id': self.campaign_id,
            'status': self.status.value,
            'campaign_name': self.campaign.name,
            'last_health_check': self.last_health_check,
            'messages_sent': self.campaign.messages_sent,
            'messages_delivered': self.campaign.messages_delivered,
            'messages_failed': self.campaign.messages_failed
        }


class CampaignManager:
    """Gerenciador global de campanhas"""
    
    def __init__(self):
        self.active_engines: Dict[str, CampaignEngine] = {}
        self.rabbitmq = RabbitMQManager()
    
    def start_campaign(self, campaign_id: str) -> CampaignEngine:
        """Inicia uma nova campanha"""
        if campaign_id in self.active_engines:
            logger.warning(f"⚠️ [MANAGER] Campanha já está ativa: {campaign_id}")
            return self.active_engines[campaign_id]
        
        engine = CampaignEngine(campaign_id)
        self.active_engines[campaign_id] = engine
        
        # Iniciar em thread separada
        threading.Thread(target=engine.start, daemon=True).start()
        
        logger.info(f"🚀 [MANAGER] Campanha iniciada: {campaign_id}")
        return engine
    
    def pause_campaign(self, campaign_id: str):
        """Pausa uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].pause()
        else:
            logger.warning(f"⚠️ [MANAGER] Campanha não encontrada: {campaign_id}")
    
    def resume_campaign(self, campaign_id: str):
        """Resume uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].resume()
        else:
            # Tentar iniciar se não estiver ativa
            self.start_campaign(campaign_id)
    
    def stop_campaign(self, campaign_id: str):
        """Para uma campanha"""
        if campaign_id in self.active_engines:
            self.active_engines[campaign_id].stop()
            del self.active_engines[campaign_id]
        else:
            logger.warning(f"⚠️ [MANAGER] Campanha não encontrada: {campaign_id}")
    
    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Retorna status de uma campanha"""
        if campaign_id in self.active_engines:
            return self.active_engines[campaign_id].get_status()
        return None
    
    def list_active_campaigns(self) -> List[str]:
        """Lista campanhas ativas"""
        return list(self.active_engines.keys())


# Instância global do gerenciador
campaign_manager = CampaignManager()
