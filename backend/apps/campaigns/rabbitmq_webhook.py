import pika
import json
import logging
from django.conf import settings
from .rabbitmq_consumer import get_rabbitmq_connection

logger = logging.getLogger(__name__)

def send_webhook_to_rabbitmq(event_data):
    """Envia evento de webhook para RabbitMQ"""
    try:
        connection = get_rabbitmq_connection()
        if not connection:
            logger.error("❌ [WEBHOOK_RABBITMQ] Conexão RabbitMQ não disponível")
            return False
            
        channel = connection.channel()
        
        # Declarar fila para webhooks
        channel.queue_declare(queue='webhook.events', durable=True)
        
        # Publicar evento
        channel.basic_publish(
            exchange='',
            routing_key='webhook.events',
            body=json.dumps(event_data, default=str),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Tornar mensagem persistente
                content_type='application/json'
            )
        )
        
        logger.info(f"✅ [WEBHOOK_RABBITMQ] Evento enviado para processamento: {event_data.get('_id')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_RABBITMQ] Erro ao enviar evento: {e}")
        return False

def start_webhook_consumer():
    """Inicia consumer para processar webhooks"""
    try:
        connection = get_rabbitmq_connection()
        if not connection:
            logger.error("❌ [WEBHOOK_CONSUMER] Conexão RabbitMQ não disponível")
            return
            
        channel = connection.channel()
        
        # Declarar fila
        channel.queue_declare(queue='webhook.events', durable=True)
        
        def process_webhook_event(ch, method, properties, body):
            try:
                event_data = json.loads(body)
                logger.info(f"🔄 [WEBHOOK_CONSUMER] Processando evento: {event_data.get('_id')}")
                
                # Processar evento
                success = process_single_webhook_event(event_data)
                
                if success:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.info(f"✅ [WEBHOOK_CONSUMER] Evento {event_data.get('_id')} processado com sucesso")
                else:
                    # Rejeitar e reenviar para retry
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    logger.warning(f"⚠️ [WEBHOOK_CONSUMER] Evento {event_data.get('_id')} rejeitado para retry")
                    
            except Exception as e:
                logger.error(f"❌ [WEBHOOK_CONSUMER] Erro ao processar evento: {e}")
                # Rejeitar sem reenviar (dead letter)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        # Configurar consumer
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue='webhook.events',
            on_message_callback=process_webhook_event
        )
        
        logger.info("🚀 [WEBHOOK_CONSUMER] Aguardando eventos de webhook...")
        channel.start_consuming()
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_CONSUMER] Erro na inicialização: {e}")

def process_single_webhook_event(event_data):
    """Processa um único evento de webhook"""
    try:
        from .models import CampaignContact
        from .mongodb_client import mongodb_client
        
        payload = event_data.get('raw_payload', {})
        whatsapp_message_id = event_data.get('whatsapp_message_id')
        event_type = event_data.get('event_type')
        
        if not whatsapp_message_id or not event_type:
            logger.warning("⚠️ [WEBHOOK_PROCESSOR] Dados incompletos no evento")
            return False
        
        # Buscar CampaignContact
        campaign_contact = CampaignContact.objects.filter(
            whatsapp_message_id=whatsapp_message_id
        ).first()
        
        if not campaign_contact:
            logger.warning(f"⚠️ [WEBHOOK_PROCESSOR] CampaignContact não encontrado: {whatsapp_message_id}")
            return False
        
        # Atualizar status
        success = update_contact_status(campaign_contact, event_type)
        
        if success:
            # Atualizar contadores da campanha
            update_campaign_counters(campaign_contact.campaign)
            
            # Marcar como processado no MongoDB
            mongodb_client.mark_as_processed(event_data['_id'])
            
            logger.info(f"✅ [WEBHOOK_PROCESSOR] Status atualizado para {campaign_contact.contact.name}: {event_type}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_PROCESSOR] Erro ao processar evento: {e}")
        return False

def update_contact_status(campaign_contact, event_type):
    """Atualiza status do contato"""
    try:
        from django.utils import timezone
        
        if event_type == 'delivered':
            campaign_contact.status = 'delivered'
            campaign_contact.delivered_at = timezone.now()
        elif event_type == 'read':
            campaign_contact.status = 'read'
            campaign_contact.read_at = timezone.now()
        elif event_type == 'failed':
            campaign_contact.status = 'failed'
            campaign_contact.failed_at = timezone.now()
            # Extrair mensagem de erro do payload se disponível
            campaign_contact.error_message = "Erro de entrega"
        
        campaign_contact.save(update_fields=['status', 'delivered_at', 'read_at', 'failed_at', 'error_message'])
        return True
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_PROCESSOR] Erro ao atualizar status: {e}")
        return False

def update_campaign_counters(campaign):
    """Atualiza contadores da campanha"""
    try:
        # Recalcular contadores
        campaign.messages_sent = campaign.campaign_contacts.filter(
            status__in=['sent', 'delivered', 'read']
        ).count()
        
        campaign.messages_delivered = campaign.campaign_contacts.filter(
            status__in=['delivered', 'read']
        ).count()
        
        campaign.messages_read = campaign.campaign_contacts.filter(
            status='read'
        ).count()
        
        campaign.messages_failed = campaign.campaign_contacts.filter(
            status='failed'
        ).count()
        
        campaign.save(update_fields=[
            'messages_sent', 'messages_delivered', 'messages_read', 'messages_failed'
        ])
        
        logger.info(f"✅ [WEBHOOK_PROCESSOR] Contadores atualizados para campanha {campaign.name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_PROCESSOR] Erro ao atualizar contadores: {e}")
        return False
