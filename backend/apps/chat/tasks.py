"""
Tasks assíncronas para Flow Chat via RabbitMQ.

Producers:
- send_message_to_evolution: Envia mensagem para Evolution API
- download_attachment: Baixa anexo da Evolution
- migrate_to_s3: Migra anexos locais para MinIO

Consumers:
- Processa mensagens das filas dedicadas ao chat
"""
import logging
import json
import asyncio
import aio_pika
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Nome das filas
QUEUE_SEND_MESSAGE = 'chat_send_message'
QUEUE_DOWNLOAD_ATTACHMENT = 'chat_download_attachment'
QUEUE_MIGRATE_S3 = 'chat_migrate_s3'


# ========== PRODUCERS (enfileirar tasks) ==========

def delay(queue_name: str, payload: dict):
    """
    Enfileira task no RabbitMQ de forma síncrona.
    Usado por código Django síncrono.
    """
    import pika
    
    try:
        # Conexão RabbitMQ
        params = pika.URLParameters(settings.RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        
        # Declara fila
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Publica mensagem
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type='application/json'
            )
        )
        
        connection.close()
        logger.info(f"✅ [RABBITMQ] Task enfileirada: {queue_name} - {payload}")
    
    except Exception as e:
        logger.error(f"❌ [RABBITMQ] Erro ao enfileirar task {queue_name}: {e}", exc_info=True)


class send_message_to_evolution:
    """Producer: Envia mensagem para Evolution API."""
    
    @staticmethod
    def delay(message_id: str):
        """Enfileira mensagem para envio."""
        delay(QUEUE_SEND_MESSAGE, {'message_id': message_id})


class download_attachment:
    """Producer: Baixa anexo da Evolution."""
    
    @staticmethod
    def delay(attachment_id: str, evolution_url: str):
        """Enfileira download de anexo."""
        delay(QUEUE_DOWNLOAD_ATTACHMENT, {
            'attachment_id': attachment_id,
            'evolution_url': evolution_url
        })


class migrate_to_s3:
    """Producer: Migra anexo local para MinIO."""
    
    @staticmethod
    def delay(attachment_id: str):
        """Enfileira migração para S3."""
        delay(QUEUE_MIGRATE_S3, {'attachment_id': attachment_id})


# ========== CONSUMER HANDLERS ==========

async def handle_send_message(message_id: str):
    """
    Handler: Envia mensagem via Evolution API.
    
    Fluxo:
    1. Busca mensagem no banco
    2. Se tiver anexos, envia via /sendFile
    3. Se tiver apenas texto, envia via /sendText
    4. Atualiza status da mensagem
    5. Broadcast via WebSocket
    """
    from apps.chat.models import Message
    from apps.connections.models import EvolutionConnection
    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async
    import httpx
    
    try:
        # Busca mensagem
        message = await sync_to_async(
            Message.objects.select_related('conversation', 'conversation__tenant').get
        )(id=message_id)
        
        # Se for nota interna, não envia
        if message.is_internal:
            message.status = 'sent'
            await sync_to_async(message.save)(update_fields=['status'])
            logger.info(f"📝 [CHAT] Nota interna criada: {message_id}")
            return
        
        # Busca conexão Evolution do tenant
        connection = await sync_to_async(
            EvolutionConnection.objects.filter(
                tenant=message.conversation.tenant,
                is_active=True,
                status='active'
            ).first
        )()
        
        if not connection:
            message.status = 'failed'
            message.error_message = 'Nenhuma conexão ativa encontrada'
            await sync_to_async(message.save)(update_fields=['status', 'error_message'])
            logger.error(f"❌ [CHAT] Sem conexão para tenant {message.conversation.tenant.name}")
            return
        
        # Prepara dados
        phone = message.conversation.contact_phone
        content = message.content
        attachment_urls = message.metadata.get('attachment_urls', []) if message.metadata else []
        
        # Envia via Evolution API
        async with httpx.AsyncClient(timeout=30.0) as client:
            base_url = connection.base_url.rstrip('/')
            headers = {
                'apikey': connection.api_key,
                'Content-Type': 'application/json'
            }
            
            # Se tiver anexos, envia cada um
            if attachment_urls:
                for url in attachment_urls:
                    payload = {
                        'number': phone.replace('+', ''),
                        'mediaMessage': {
                            'mediaUrl': url
                        }
                    }
                    if content:
                        payload['mediaMessage']['caption'] = content
                    
                    response = await client.post(
                        f"{base_url}/message/sendMedia/{connection.name}",
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    message.message_id = data.get('key', {}).get('id')
                    logger.info(f"✅ [CHAT] Mídia enviada: {message_id}")
            
            # Envia texto (se não tiver anexo ou como caption separado)
            if content and not attachment_urls:
                payload = {
                    'number': phone.replace('+', ''),
                    'textMessage': {
                        'text': content
                    }
                }
                
                response = await client.post(
                    f"{base_url}/message/sendText/{connection.name}",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                message.message_id = data.get('key', {}).get('id')
                logger.info(f"✅ [CHAT] Texto enviado: {message_id}")
        
        # Atualiza status
        message.status = 'sent'
        message.evolution_status = 'sent'
        await sync_to_async(message.save)(update_fields=['status', 'evolution_status', 'message_id'])
        
        # Broadcast via WebSocket
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
        
        from apps.chat.api.serializers import MessageSerializer
        message_data = await sync_to_async(lambda: MessageSerializer(message).data)()
        
        await channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_status_update',
                'message_id': str(message.id),
                'status': 'sent',
                'message': message_data
            }
        )
    
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro ao enviar mensagem {message_id}: {e}", exc_info=True)
        
        # Marca como falha
        try:
            message.status = 'failed'
            message.error_message = str(e)
            await sync_to_async(message.save)(update_fields=['status', 'error_message'])
        except:
            pass


async def handle_download_attachment(attachment_id: str, evolution_url: str):
    """
    Handler: Baixa anexo da Evolution e salva localmente.
    """
    from apps.chat.models import MessageAttachment
    from apps.chat.utils.storage import download_and_save_attachment
    from asgiref.sync import sync_to_async
    
    try:
        attachment = await sync_to_async(
            MessageAttachment.objects.select_related('tenant').get
        )(id=attachment_id)
        
        # Download e save
        success = await download_and_save_attachment(attachment, evolution_url)
        
        if success:
            logger.info(f"✅ [CHAT] Anexo baixado: {attachment_id}")
            
            # Enfileira migração para S3 (após 1h, por exemplo)
            # Pode ser feito via cron ou aqui mesmo
            migrate_to_s3.delay(attachment_id)
        else:
            logger.error(f"❌ [CHAT] Falha ao baixar anexo: {attachment_id}")
    
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro no download do anexo {attachment_id}: {e}", exc_info=True)


async def handle_migrate_s3(attachment_id: str):
    """
    Handler: Migra anexo local para MinIO.
    """
    from apps.chat.models import MessageAttachment
    from apps.chat.utils.storage import migrate_to_minio
    from asgiref.sync import sync_to_async
    
    try:
        attachment = await sync_to_async(
            MessageAttachment.objects.get
        )(id=attachment_id)
        
        # Se já está no S3, ignora
        if attachment.storage_type == 's3':
            logger.info(f"ℹ️ [CHAT] Anexo {attachment_id} já está no S3")
            return
        
        # Migra
        success = await migrate_to_minio(attachment)
        
        if success:
            logger.info(f"✅ [CHAT] Anexo migrado para S3: {attachment_id}")
        else:
            logger.error(f"❌ [CHAT] Falha ao migrar anexo para S3: {attachment_id}")
    
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro ao migrar anexo {attachment_id}: {e}", exc_info=True)


# ========== CONSUMER (processa filas) ==========

async def start_chat_consumers():
    """
    Inicia consumers RabbitMQ para processar filas do chat.
    Roda em background via management command ou ASGI lifespan.
    """
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        
        # Declara filas
        queue_send = await channel.declare_queue(QUEUE_SEND_MESSAGE, durable=True)
        queue_download = await channel.declare_queue(QUEUE_DOWNLOAD_ATTACHMENT, durable=True)
        queue_migrate = await channel.declare_queue(QUEUE_MIGRATE_S3, durable=True)
        
        logger.info("✅ [CHAT CONSUMER] Filas declaradas")
        
        # Consumer: send_message
        async def on_send_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await handle_send_message(payload['message_id'])
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro send_message: {e}", exc_info=True)
        
        # Consumer: download_attachment
        async def on_download_attachment(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await handle_download_attachment(
                        payload['attachment_id'],
                        payload['evolution_url']
                    )
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro download_attachment: {e}", exc_info=True)
        
        # Consumer: migrate_to_s3
        async def on_migrate_s3(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await handle_migrate_s3(payload['attachment_id'])
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro migrate_s3: {e}", exc_info=True)
        
        # Inicia consumo
        await queue_send.consume(on_send_message)
        await queue_download.consume(on_download_attachment)
        await queue_migrate.consume(on_migrate_s3)
        
        logger.info("🚀 [CHAT CONSUMER] Consumers iniciados e aguardando mensagens")
        
        # Mantém rodando
        await asyncio.Future()
    
    except Exception as e:
        logger.error(f"❌ [CHAT CONSUMER] Erro ao iniciar consumers: {e}", exc_info=True)


# Para rodar o consumer
if __name__ == '__main__':
    import asyncio
    asyncio.run(start_chat_consumers())

