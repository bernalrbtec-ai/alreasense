"""
Tasks assíncronas para Flow Chat via RabbitMQ.

Producers:
- send_message_to_evolution: Envia mensagem para Evolution API
- process_profile_pic: Processa foto de perfil do WhatsApp
- process_incoming_media: Processa mídia recebida do WhatsApp
- process_uploaded_file: Processa arquivo enviado pelo usuário

Consumers:
- Processa mensagens das filas dedicadas ao chat
"""
import logging
import json
import asyncio
import aio_pika
import httpx
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Nome das filas
QUEUE_SEND_MESSAGE = 'chat_send_message'
QUEUE_DOWNLOAD_ATTACHMENT = 'chat_download_attachment'
QUEUE_MIGRATE_S3 = 'chat_migrate_s3'
QUEUE_FETCH_PROFILE_PIC = 'chat_fetch_profile_pic'
QUEUE_PROCESS_INCOMING_MEDIA = 'chat_process_incoming_media'
QUEUE_PROCESS_UPLOADED_FILE = 'chat_process_uploaded_file'


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


class fetch_profile_pic:
    """Producer: Busca foto de perfil via Evolution API."""
    
    @staticmethod
    def delay(conversation_id: str, phone: str):
        """Enfileira busca de foto de perfil."""
        delay(QUEUE_FETCH_PROFILE_PIC, {
            'conversation_id': conversation_id,
            'phone': phone
        })


class process_profile_pic:
    """Producer: Processa foto de perfil do WhatsApp."""
    
    @staticmethod
    def delay(tenant_id: str, phone: str, profile_url: str):
        """Enfileira processamento de foto de perfil."""
        delay(QUEUE_FETCH_PROFILE_PIC, {
            'tenant_id': tenant_id,
            'phone': phone,
            'profile_url': profile_url
        })


class process_incoming_media:
    """Producer: Processa mídia recebida do WhatsApp."""
    
    @staticmethod
    def delay(tenant_id: str, message_id: str, media_url: str, media_type: str):
        """Enfileira processamento de mídia recebida."""
        delay(QUEUE_PROCESS_INCOMING_MEDIA, {
            'tenant_id': tenant_id,
            'message_id': message_id,
            'media_url': media_url,
            'media_type': media_type
        })


class process_uploaded_file:
    """Producer: Processa arquivo enviado pelo usuário."""
    
    @staticmethod
    def delay(tenant_id: str, file_data: str, filename: str, content_type: str):
        """Enfileira processamento de arquivo enviado (base64)."""
        delay(QUEUE_PROCESS_UPLOADED_FILE, {
            'tenant_id': tenant_id,
            'file_data': file_data,  # base64
            'filename': filename,
            'content_type': content_type
        })


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
    from apps.notifications.models import WhatsAppInstance
    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async
    import httpx
    
    logger.info(f"📤 [CHAT ENVIO] Iniciando envio de mensagem...")
    logger.info(f"   Message ID: {message_id}")
    
    try:
        # Busca mensagem
        message = await sync_to_async(
            Message.objects.select_related('conversation', 'conversation__tenant').get
        )(id=message_id)
        
        logger.info(f"✅ [CHAT ENVIO] Mensagem encontrada no banco")
        logger.info(f"   Conversa: {message.conversation.contact_phone}")
        logger.info(f"   Tenant: {message.conversation.tenant.name}")
        logger.info(f"   Content: {message.content[:50]}...")
        
        # Se for nota interna, não envia
        if message.is_internal:
            message.status = 'sent'
            await sync_to_async(message.save)(update_fields=['status'])
            logger.info(f"📝 [CHAT ENVIO] Nota interna criada (não enviada ao WhatsApp)")
            return
        
        # Busca instância WhatsApp ativa do tenant (mesmo modelo das campanhas)
        logger.info(f"🔍 [CHAT ENVIO] Buscando instância WhatsApp ativa...")
        
        instance = await sync_to_async(
            WhatsAppInstance.objects.filter(
                tenant=message.conversation.tenant,
                is_active=True
            ).first
        )()
        
        if not instance:
            message.status = 'failed'
            message.error_message = 'Nenhuma instância WhatsApp ativa encontrada'
            await sync_to_async(message.save)(update_fields=['status', 'error_message'])
            logger.error(f"❌ [CHAT ENVIO] Nenhuma instância WhatsApp ativa!")
            logger.error(f"   Tenant: {message.conversation.tenant.name}")
            return
        
        logger.info(f"✅ [CHAT ENVIO] Instância encontrada!")
        logger.info(f"   Nome: {instance.friendly_name}")
        logger.info(f"   UUID: {instance.instance_name}")
        logger.info(f"   API URL: {instance.api_url}")
        
        # Prepara dados
        conversation = message.conversation
        
        # 🔍 PARA GRUPOS: usar group_id ao invés de contact_phone
        if conversation.conversation_type == 'group' and conversation.group_metadata:
            phone = conversation.group_metadata.get('group_id', conversation.contact_phone)
            # Remover '+' se tiver (grupos não usam +)
            phone = phone.replace('+', '')
        else:
            phone = conversation.contact_phone
        
        content = message.content
        attachment_urls = message.metadata.get('attachment_urls', []) if message.metadata else []
        
        logger.info(f"📱 [CHAT ENVIO] Telefone/Grupo: {phone}")
        logger.info(f"   Tipo: {conversation.conversation_type}")
        
        # Buscar attachments para obter mime_type
        attachments_list = []
        if attachment_urls:
            from apps.chat.models import MessageAttachment
            attachments_list = await sync_to_async(list)(
                MessageAttachment.objects.filter(message=message)
            )
        
        # Envia via Evolution API
        async with httpx.AsyncClient(timeout=30.0) as client:
            base_url = instance.api_url.rstrip('/')
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            
            # Se tiver anexos, envia cada um
            if attachment_urls:
                for idx, url in enumerate(attachment_urls):
                    # Detectar mediatype e filename baseado no attachment
                    mime_type = 'application/pdf'  # default
                    filename = 'file'
                    
                    if attachments_list and idx < len(attachments_list):
                        mime_type = attachments_list[idx].mime_type
                        filename = attachments_list[idx].original_filename
                    
                    # Mapear mime_type para mediatype da Evolution API
                    is_audio = mime_type.startswith('audio/')
                    
                    # 🎤 ÁUDIO: Usar audioMessage com PTT para aparecer como "gravado"
                    if is_audio:
                        # Estrutura específica para PTT (Push-To-Talk - áudio gravado)
                        # https://doc.evolution-api.com/v2/pt/send-messages/send-audios
                        payload = {
                            'number': phone,
                            'audioMessage': {
                                'audio': url,  # URL do arquivo no S3
                                'ptt': True    # 🎯 FLAG para aparecer como áudio gravado!
                            }
                        }
                        logger.info(f"🎤 [CHAT] Enviando como PTT (áudio gravado)")
                    else:
                        # 📎 OUTROS TIPOS: Usar sendMedia normal
                        if mime_type.startswith('image/'):
                            mediatype = 'image'
                        elif mime_type.startswith('video/'):
                            mediatype = 'video'
                        else:
                            mediatype = 'document'
                        
                        # ✅ Evolution API NÃO usa mediaMessage wrapper!
                        # Estrutura correta: direto no root
                        payload = {
                            'number': phone,
                            'media': url,           # URL do arquivo
                            'mediatype': mediatype,  # lowercase!
                            'fileName': filename     # Nome do arquivo
                        }
                        if content:
                            payload['caption'] = content  # Caption direto no root também
                    
                    logger.info(f"🔍 [CHAT] Enviando mídia para Evolution API:")
                    logger.info(f"   URL: {base_url}/message/sendMedia/{instance.instance_name}")
                    logger.info(f"   Payload: {payload}")
                    
                    response = await client.post(
                        f"{base_url}/message/sendMedia/{instance.instance_name}",
                        headers=headers,
                        json=payload
                    )
                    
                    logger.info(f"🔍 [CHAT] Resposta Evolution API: {response.status_code}")
                    logger.info(f"   Body: {response.text[:500]}")
                    
                    response.raise_for_status()
                    
                    data = response.json()
                    message.message_id = data.get('key', {}).get('id')
                    logger.info(f"✅ [CHAT] Mídia enviada: {message_id}")
            
            # Envia texto (se não tiver anexo ou como caption separado)
            if content and not attachment_urls:
                # 🔍 PARA GRUPOS: não formatar (já vem como "120363...@g.us")
                # Para contatos individuais: adicionar + se não tiver
                if conversation.conversation_type == 'group':
                    formatted_phone = phone  # Grupos: usar como está (ex: "120363...@g.us")
                else:
                    formatted_phone = phone if phone.startswith('+') else f'+{phone}'
                
                # Usar mesmo formato das campanhas
                payload = {
                    'number': formatted_phone,
                    'text': content,
                    'instance': instance.instance_name
                }
                
                logger.info(f"📤 [CHAT ENVIO] Enviando mensagem de texto para Evolution API...")
                logger.info(f"   Tipo: {conversation.conversation_type}")
                logger.info(f"   URL: {base_url}/message/sendText/{instance.instance_name}")
                logger.info(f"   Phone original: {phone}")
                logger.info(f"   Phone formatado: {formatted_phone}")
                logger.info(f"   Text: {content[:50]}...")
                logger.info(f"   Payload completo: {payload}")
                
                response = await client.post(
                    f"{base_url}/message/sendText/{instance.instance_name}",
                    headers=headers,
                    json=payload
                )
                
                logger.info(f"📥 [CHAT ENVIO] Resposta da Evolution API:")
                logger.info(f"   Status: {response.status_code}")
                logger.info(f"   Body: {response.text[:300]}")
                
                response.raise_for_status()
                
                data = response.json()
                message.message_id = data.get('key', {}).get('id')
                logger.info(f"✅ [CHAT ENVIO] Mensagem enviada com sucesso!")
                logger.info(f"   Message ID Evolution: {message.message_id}")
        
        # Atualiza status
        message.status = 'sent'
        message.evolution_status = 'sent'
        await sync_to_async(message.save)(update_fields=['status', 'evolution_status', 'message_id'])
        
        logger.info(f"💾 [CHAT ENVIO] Status atualizado no banco para 'sent'")
        
        # Broadcast via WebSocket (convertendo UUIDs para string)
        logger.info(f"📡 [CHAT ENVIO] Preparando broadcast via WebSocket...")
        
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
        
        logger.info(f"   Room: {room_group_name}")
        
        from apps.chat.api.serializers import MessageSerializer
        message_data = await sync_to_async(lambda: MessageSerializer(message).data)()
        
        # Converter UUIDs para string para serialização msgpack
        def convert_uuids_to_str(obj):
            """Recursivamente converte UUIDs para string."""
            import uuid
            if isinstance(obj, uuid.UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids_to_str(item) for item in obj]
            return obj
        
        message_data_serializable = convert_uuids_to_str(message_data)
        
        await channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_status_update',
                'message_id': str(message.id),
                'status': 'sent',
                'message': message_data_serializable
            }
        )
        
        logger.info(f"✅ [CHAT ENVIO] Mensagem enviada e broadcast com sucesso!")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Phone: {message.conversation.contact_phone}")
        logger.info(f"   Status: {message.status}")
    
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
    
    Melhorias:
    - Retry automático (3 tentativas)
    - Validação de tamanho (máx 50MB)
    - Timeout de 2 minutos
    - Backoff exponencial
    """
    from apps.chat.models import MessageAttachment
    from apps.chat.utils.storage import download_and_save_attachment
    from asgiref.sync import sync_to_async
    import httpx
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_RETRIES = 3
    TIMEOUT = 120.0  # 2 minutos
    
    logger.info(f"📥 [DOWNLOAD] Iniciando download de anexo...")
    logger.info(f"   Attachment ID: {attachment_id}")
    logger.info(f"   URL: {evolution_url[:100]}...")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 [DOWNLOAD] Tentativa {attempt}/{MAX_RETRIES}")
            
            # Busca anexo
            attachment = await sync_to_async(
                MessageAttachment.objects.select_related('tenant').get
            )(id=attachment_id)
            
            # Validar tamanho primeiro (HEAD request)
            async with httpx.AsyncClient(timeout=10.0) as client:
                head_response = await client.head(evolution_url)
                content_length = int(head_response.headers.get('content-length', 0))
                
                logger.info(f"📊 [DOWNLOAD] Tamanho do arquivo: {content_length / 1024 / 1024:.2f}MB")
                
                if content_length > MAX_FILE_SIZE:
                    logger.error(f"❌ [DOWNLOAD] Arquivo muito grande! Máximo: 50MB")
                    attachment.error_message = f"Arquivo muito grande ({content_length / 1024 / 1024:.2f}MB). Máximo: 50MB"
                    await sync_to_async(attachment.save)(update_fields=['error_message'])
                    return False
            
            # Download
            success = await download_and_save_attachment(
                attachment, 
                evolution_url
            )
            
            if success:
                logger.info(f"✅ [DOWNLOAD] Anexo baixado com sucesso!")
                logger.info(f"   Attachment ID: {attachment_id}")
                logger.info(f"   Tentativa: {attempt}/{MAX_RETRIES}")
                
                # Enfileira migração para S3
                migrate_to_s3.delay(attachment_id)
                return True
            else:
                logger.warning(f"⚠️ [DOWNLOAD] Falha na tentativa {attempt}")
                if attempt < MAX_RETRIES:
                    wait_time = 2 ** attempt  # Backoff exponencial: 2s, 4s, 8s
                    logger.info(f"⏳ [DOWNLOAD] Aguardando {wait_time}s antes de retry...")
                    await asyncio.sleep(wait_time)
                    continue
        
        except httpx.TimeoutException:
            logger.error(f"⏱️ [DOWNLOAD] Timeout na tentativa {attempt}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
        
        except Exception as e:
            logger.error(f"❌ [DOWNLOAD] Erro na tentativa {attempt}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
    
    logger.error(f"❌ [DOWNLOAD] Falha após {MAX_RETRIES} tentativas!")
    logger.error(f"   Attachment ID: {attachment_id}")
    return False


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


async def handle_fetch_profile_pic(conversation_id: str, phone: str):
    """
    Handler: Busca foto de perfil via Evolution API e salva.
    
    Fluxo:
    1. Busca conversa e instância Evolution
    2. Chama endpoint /chat/fetchProfilePictureUrl
    3. Se retornar URL, salva no campo profile_pic_url
    4. Broadcast atualização via WebSocket
    """
    from apps.chat.models import Conversation
    from apps.connections.models import EvolutionConnection
    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async
    import httpx
    
    logger.info(f"📸 [PROFILE PIC] Buscando foto de perfil...")
    logger.info(f"   Conversation ID: {conversation_id}")
    logger.info(f"   Phone: {phone}")
    
    try:
        # Busca conversa
        conversation = await sync_to_async(
            Conversation.objects.select_related('tenant').get
        )(id=conversation_id)
        
        # Busca instância WhatsApp ativa
        from apps.notifications.models import WhatsAppInstance
        from apps.connections.models import EvolutionConnection
        
        wa_instance = await sync_to_async(
            WhatsAppInstance.objects.filter(
                tenant=conversation.tenant,
                is_active=True,
                status='active'
            ).first
        )()
        
        if not wa_instance:
            logger.warning(f"⚠️ [PROFILE PIC] Nenhuma instância WhatsApp ativa")
            return
        
        # Buscar servidor Evolution
        evolution_server = await sync_to_async(
            EvolutionConnection.objects.filter(is_active=True).first
        )()
        
        if not evolution_server:
            logger.warning(f"⚠️ [PROFILE PIC] Servidor Evolution não configurado")
            return
        
        logger.info(f"✅ [PROFILE PIC] Instância encontrada: {wa_instance.friendly_name}")
        
        # Formatar telefone (sem + e sem @s.whatsapp.net)
        clean_phone = phone.replace('+', '')
        
        # Endpoint Evolution API
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance_name}"
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"📡 [PROFILE PIC] Chamando Evolution API...")
        logger.info(f"   Endpoint: {endpoint}")
        logger.info(f"   Phone (clean): {clean_phone}")
        
        # Buscar foto
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                endpoint,
                params={'number': clean_phone},
                headers=headers
            )
            
            logger.info(f"📥 [PROFILE PIC] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📦 [PROFILE PIC] Response data: {data}")
                
                # Extrair URL da foto
                profile_url = (
                    data.get('profilePictureUrl') or
                    data.get('profilePicUrl') or
                    data.get('url') or
                    data.get('picture')
                )
                
                if profile_url:
                    logger.info(f"✅ [PROFILE PIC] Foto encontrada!")
                    logger.info(f"   URL: {profile_url[:100]}...")
                    
                    # Atualizar conversa
                    conversation.profile_pic_url = profile_url
                    await sync_to_async(conversation.save)(update_fields=['profile_pic_url'])
                    
                    # Broadcast atualização via WebSocket
                    try:
                        from apps.chat.api.serializers import ConversationSerializer
                        conv_data = await sync_to_async(lambda: ConversationSerializer(conversation).data)()
                        
                        # Converter UUIDs
                        def convert_uuids_to_str(obj):
                            import uuid
                            if isinstance(obj, uuid.UUID):
                                return str(obj)
                            elif isinstance(obj, dict):
                                return {k: convert_uuids_to_str(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [convert_uuids_to_str(item) for item in obj]
                            return obj
                        
                        conv_data_serializable = convert_uuids_to_str(conv_data)
                        
                        channel_layer = get_channel_layer()
                        tenant_group = f"chat_tenant_{conversation.tenant_id}"
                        
                        await channel_layer.group_send(
                            tenant_group,
                            {
                                'type': 'conversation_updated',
                                'conversation': conv_data_serializable
                            }
                        )
                        
                        logger.info(f"📡 [PROFILE PIC] Atualização broadcast via WebSocket")
                    except Exception as e:
                        logger.error(f"❌ [PROFILE PIC] Erro no broadcast: {e}")
                    
                    logger.info(f"✅ [PROFILE PIC] Foto de perfil atualizada com sucesso!")
                else:
                    logger.warning(f"⚠️ [PROFILE PIC] Response não contém URL de foto")
                    logger.warning(f"   Data recebida: {data}")
            else:
                logger.warning(f"⚠️ [PROFILE PIC] Status não OK: {response.status_code}")
                logger.warning(f"   Response: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ [PROFILE PIC] Erro ao buscar foto: {e}", exc_info=True)


# ========== CONSUMER (processa filas) ==========

async def start_chat_consumers():
    """
    Inicia consumers RabbitMQ para processar filas do chat.
    Roda em background via management command ou ASGI lifespan.
    """
    try:
        # ✅ CORREÇÃO: Usar mesmos parâmetros do campaigns consumer
        import re
        import os
        
        # 🔍 DEBUG: Verificar variáveis de ambiente diretamente
        logger.info("=" * 80)
        logger.info("🔍 [CHAT CONSUMER DEBUG] Verificando variáveis RabbitMQ")
        logger.info("=" * 80)
        
        env_private = os.environ.get('RABBITMQ_PRIVATE_URL', 'NOT_SET')
        env_public = os.environ.get('RABBITMQ_URL', 'NOT_SET')
        env_user = os.environ.get('RABBITMQ_DEFAULT_USER', 'NOT_SET')
        env_pass = os.environ.get('RABBITMQ_DEFAULT_PASS', 'NOT_SET')
        
        logger.info(f"RABBITMQ_PRIVATE_URL presente: {env_private != 'NOT_SET'}")
        logger.info(f"RABBITMQ_URL presente: {env_public != 'NOT_SET'}")
        logger.info(f"RABBITMQ_DEFAULT_USER: {env_user}")
        logger.info(f"RABBITMQ_DEFAULT_PASS presente: {env_pass != 'NOT_SET'} (len={len(env_pass) if env_pass != 'NOT_SET' else 0})")
        
        # ✅ FIX FINAL: Usar URL DIRETAMENTE como Campaigns Consumer
        # Railway já fornece URL com encoding correto
        # Aplicar encoding novamente causa DOUBLE ENCODING e falha de autenticação
        rabbitmq_url = settings.RABBITMQ_URL
        
        # Log seguro (mascarar credenciais)
        safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)
        
        logger.info(f"settings.RABBITMQ_URL: {safe_url}")
        logger.info(f"URL length: {len(rabbitmq_url)}")
        logger.info("=" * 80)
        logger.info(f"🔍 [CHAT CONSUMER] Conectando ao RabbitMQ: {safe_url}")
        logger.info(f"🔍 [CHAT CONSUMER] Usando parâmetros de conexão robustos...")
        
        connection = await aio_pika.connect_robust(
            rabbitmq_url,
            heartbeat=0,  # Desabilitar heartbeat (mesmo do campaigns)
            blocked_connection_timeout=0,
            socket_timeout=10,
            retry_delay=1,
            connection_attempts=1
        )
        logger.info("✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida com sucesso!")
        
        channel = await connection.channel()
        logger.info("✅ [CHAT CONSUMER] Channel criado com sucesso!")
        
        # Declara filas
        queue_send = await channel.declare_queue(QUEUE_SEND_MESSAGE, durable=True)
        queue_download = await channel.declare_queue(QUEUE_DOWNLOAD_ATTACHMENT, durable=True)
        queue_migrate = await channel.declare_queue(QUEUE_MIGRATE_S3, durable=True)
        queue_profile_pic = await channel.declare_queue(QUEUE_FETCH_PROFILE_PIC, durable=True)
        
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
        
        # Consumer: fetch_profile_pic
        async def on_fetch_profile_pic(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await handle_fetch_profile_pic(
                        payload['conversation_id'],
                        payload['phone']
                    )
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro fetch_profile_pic: {e}", exc_info=True)
        
        # Inicia consumo
        await queue_send.consume(on_send_message)
        await queue_download.consume(on_download_attachment)
        await queue_migrate.consume(on_migrate_s3)
        await queue_profile_pic.consume(on_fetch_profile_pic)
        
        logger.info("🚀 [CHAT CONSUMER] Consumers iniciados e aguardando mensagens")
        
        # Mantém rodando
        await asyncio.Future()
    
    except Exception as e:
        error_msg = str(e)
        
        # ✅ DIAGNÓSTICO: Erro de autenticação RabbitMQ
        if 'ACCESS_REFUSED' in error_msg or 'authentication' in error_msg.lower():
            logger.error("=" * 80)
            logger.error("🚨 [CHAT CONSUMER] ERRO DE AUTENTICAÇÃO RABBITMQ")
            logger.error("=" * 80)
            logger.error(f"❌ Erro: {error_msg}")
            logger.error("")
            logger.error("📋 POSSÍVEIS CAUSAS:")
            logger.error("1. Credenciais RabbitMQ incorretas na variável de ambiente")
            logger.error("2. RABBITMQ_PRIVATE_URL pode estar usando credenciais antigas")
            logger.error("3. Usuário RabbitMQ pode não ter permissões suficientes")
            logger.error("")
            logger.error("🔧 SOLUÇÕES:")
            logger.error("1. Verificar variáveis no Railway:")
            logger.error("   - RABBITMQ_URL")
            logger.error("   - RABBITMQ_PRIVATE_URL")
            logger.error("2. Comparar com credenciais do campaigns consumer (que funciona)")
            logger.error("3. Regenerar credenciais RabbitMQ no Railway se necessário")
            logger.error("=" * 80)
        else:
            logger.error(f"❌ [CHAT CONSUMER] Erro ao iniciar consumers: {e}", exc_info=True)


# Para rodar o consumer
if __name__ == '__main__':
    import asyncio
    asyncio.run(start_chat_consumers())

