"""
Tasks assíncronas para Flow Chat.

✅ ARQUITETURA HÍBRIDA:
- Redis Queue: Para tasks de latência crítica (send_message, fetch_profile_pic, fetch_group_info)
  - Performance: 10x mais rápido que RabbitMQ (2-6ms vs 15-65ms)
  - Uso: Envio de mensagens, busca de fotos de perfil, info de grupos
  
- RabbitMQ: Apenas para process_incoming_media (durabilidade crítica)
  - Uso: Processamento de mídia recebida (requer garantia de durabilidade)
  - Motivo: RabbitMQ oferece garantias de persistência mais robustas para mídia

Producers:
- send_message_to_evolution: Envia mensagem para Evolution API (Redis)
- process_profile_pic: Processa foto de perfil do WhatsApp (Redis)
- process_incoming_media: Processa mídia recebida do WhatsApp (RabbitMQ)
- process_uploaded_file: Processa arquivo enviado pelo usuário

Consumers:
- Redis Consumer: Processa filas Redis (apps.chat.redis_consumer)
- RabbitMQ Consumer: Processa fila de mídia (apps.chat.media_tasks)
"""
import logging
import json
import asyncio
import aio_pika
import httpx
from typing import Optional
from django.conf import settings
from django.core.cache import cache
from apps.chat.webhooks import send_read_receipt
from apps.chat.utils.instance_state import (
    should_defer_instance,
    InstanceTemporarilyUnavailable,
    compute_backoff,
)

logger = logging.getLogger(__name__)
send_logger = logging.getLogger("flow.chat.send")
read_logger = logging.getLogger("flow.chat.read")

# Nome das filas
QUEUE_SEND_MESSAGE = 'chat_send_message'
# ❌ QUEUE_DOWNLOAD_ATTACHMENT e QUEUE_MIGRATE_S3 REMOVIDOS - fluxo antigo (local → S3)
# ✅ Novo fluxo: process_incoming_media faz download direto para S3 + Redis cache
QUEUE_FETCH_PROFILE_PIC = 'chat_fetch_profile_pic'
QUEUE_PROCESS_INCOMING_MEDIA = 'chat_process_incoming_media'
QUEUE_PROCESS_UPLOADED_FILE = 'chat_process_uploaded_file'
QUEUE_FETCH_GROUP_INFO = 'chat_fetch_group_info'  # ✅ NOVO: Busca informações de grupo de forma assíncrona


def _mask_digits(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    digits = ''.join(ch for ch in value if ch.isdigit())
    if not digits:
        return value
    suffix = digits[-4:] if len(digits) > 4 else digits
    return f"***{suffix}"


def _mask_remote_jid(remote_jid: str) -> str:
    if not remote_jid or not isinstance(remote_jid, str):
        return remote_jid
    if '@' not in remote_jid:
        return _mask_digits(remote_jid)
    user, domain = remote_jid.split('@', 1)
    return f"{_mask_digits(user)}@{domain}"


def _truncate_text(value: str, limit: int = 120) -> str:
    if not isinstance(value, str):
        return value
    return value if len(value) <= limit else f"{value[:limit]}…"


def mask_sensitive_data(data, parent_key: str = ""):
    sensitive_keys_phone = {'number', 'phone', 'contact_phone'}
    sensitive_keys_remote = {'remoteJid', 'jid', 'participant'}
    sensitive_keys_ids = {'id', 'messageId', 'message_id', 'keyId', 'key_id'}
    sensitive_keys_text = {'text', 'content', 'body'}

    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key in sensitive_keys_phone or key_lower in sensitive_keys_phone:
                masked[key] = _mask_digits(value) if isinstance(value, str) else value
            elif key in sensitive_keys_remote or key_lower in sensitive_keys_remote:
                masked[key] = _mask_remote_jid(value) if isinstance(value, str) else value
            elif key in sensitive_keys_ids or key_lower in sensitive_keys_ids:
                masked[key] = _mask_digits(value) if isinstance(value, str) else value
            elif key in sensitive_keys_text or key_lower in sensitive_keys_text:
                masked[key] = _truncate_text(value)
            else:
                masked[key] = mask_sensitive_data(value, key)
        return masked

    if isinstance(data, list):
        return [mask_sensitive_data(item, parent_key) for item in data]

    return data


# ========== PRODUCERS (enfileirar tasks) ==========

# ✅ MIGRAÇÃO: Producers Redis para filas de latência crítica
from apps.chat.redis_queue import (
    enqueue_message,
    REDIS_QUEUE_SEND_MESSAGE,
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO,
    REDIS_QUEUE_MARK_AS_READ
)
from apps.chat.utils.instance_state import should_defer_instance

# ❌ REMOVIDO: Função delay() RabbitMQ (substituída por Redis)
# Mantida apenas para process_incoming_media (durabilidade crítica)

def delay_rabbitmq(queue_name: str, payload: dict):
    """
    Enfileira task no RabbitMQ de forma síncrona.
    ⚠️ USAR APENAS para process_incoming_media (durabilidade crítica).
    Para outras filas, usar Redis (10x mais rápido).
    """
    import pika
    
    logger.info(f"🚀 [RABBITMQ] Tentando enfileirar: {queue_name}")
    logger.info(f"   Payload keys: {list(payload.keys())}")
    
    try:
        # Conexão RabbitMQ
        logger.debug(f"🔗 [RABBITMQ] Conectando ao RabbitMQ...")
        params = pika.URLParameters(settings.RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        logger.debug(f"✅ [RABBITMQ] Conectado!")
        
        # Declara fila
        channel.queue_declare(queue=queue_name, durable=True)
        logger.debug(f"📦 [RABBITMQ] Fila '{queue_name}' declarada")
        
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
        logger.info(f"✅ [RABBITMQ] Mensagem publicada na fila '{queue_name}'")
        
        connection.close()
        logger.info(f"✅ [RABBITMQ] Task enfileirada com sucesso: {queue_name}")
    
    except Exception as e:
        logger.error(f"❌ [RABBITMQ] ERRO CRÍTICO ao enfileirar task {queue_name}: {e}", exc_info=True)
        raise  # Re-raise para ver o erro


class send_message_to_evolution:
    """Producer: Envia mensagem para Evolution API (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(message_id: str):
        """Enfileira mensagem para envio (Redis)."""
        enqueue_message(REDIS_QUEUE_SEND_MESSAGE, {'message_id': message_id})


# ❌ download_attachment e migrate_to_s3 REMOVIDOS
# Motivo: Fluxo antigo de 2 etapas (local → S3) foi substituído por process_incoming_media
# que faz download direto para S3 + cache Redis em uma única etapa


class fetch_profile_pic:
    """Producer: Busca foto de perfil via Evolution API (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(conversation_id: str, phone: str):
        """Enfileira busca de foto de perfil (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, {
            'conversation_id': conversation_id,
            'phone': phone
        })


class process_profile_pic:
    """Producer: Processa foto de perfil do WhatsApp (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(tenant_id: str, phone: str, profile_url: str):
        """Enfileira processamento de foto de perfil (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_PROFILE_PIC, {
            'tenant_id': tenant_id,
            'phone': phone,
            'profile_url': profile_url
        })


class process_incoming_media:
    """
    Producer: Processa mídia recebida do WhatsApp (RabbitMQ - durabilidade crítica).
    
    ⚠️ MANTIDO EM RABBITMQ por questões de resiliência:
    - Durabilidade garantida (mensagens não são perdidas se servidor cair)
    - Persistência em disco (sobrevive a reinicializações)
    - Não é latência crítica (pode ser processado assincronamente)
    - Perda de mídia é crítica (não pode ser reprocessada)
    """
    
    @staticmethod
    def delay(tenant_id: str, message_id: str, media_url: str, media_type: str, 
              instance_name: str = None, api_key: str = None, evolution_api_url: str = None,
              message_key: dict = None):
        """Enfileira processamento de mídia recebida (RabbitMQ)."""
        delay_rabbitmq(QUEUE_PROCESS_INCOMING_MEDIA, {
            'tenant_id': tenant_id,
            'message_id': message_id,
            'media_url': media_url,
            'media_type': media_type,
            'instance_name': instance_name,
            'api_key': api_key,
            'evolution_api_url': evolution_api_url,
            'message_key': message_key
        })


class process_uploaded_file:
    """Producer: Processa arquivo enviado pelo usuário."""
    
    @staticmethod
    def delay(tenant_id: str, file_data: str, filename: str, content_type: str):
        """Enfileira processamento de arquivo enviado (base64)."""
        delay_rabbitmq(QUEUE_PROCESS_UPLOADED_FILE, {
            'tenant_id': tenant_id,
            'file_data': file_data,  # base64
            'filename': filename,
            'content_type': content_type
        })


class fetch_group_info:
    """Producer: Busca info de grupo via Evolution API (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(conversation_id: str, group_jid: str, instance_name: str, api_key: str, base_url: str):
        """Enfileira busca de info de grupo (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_GROUP_INFO, {
            'conversation_id': conversation_id,
            'group_jid': group_jid,
            'instance_name': instance_name,
            'api_key': api_key,
            'base_url': base_url
        })


def enqueue_mark_as_read(conversation_id: str, message_id: str):
    """Producer auxiliar: enfileira envio de read receipt."""
    enqueue_message(REDIS_QUEUE_MARK_AS_READ, {
        'conversation_id': conversation_id,
        'message_id': message_id
    })


# ========== CONSUMER HANDLERS ==========

async def handle_send_message(message_id: str, retry_count: int = 0):
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
    from channels.db import database_sync_to_async
    from asgiref.sync import sync_to_async
    import httpx
    
    send_logger.info("📤 [CHAT ENVIO] Iniciando envio | message_id=%s retry=%s", message_id, retry_count)

    log = send_logger

    try:
        # Busca mensagem com todos os relacionamentos necessários para serialização
        message = await sync_to_async(
            Message.objects.select_related(
                'conversation', 
                'conversation__tenant', 
                'sender',
                'sender__tenant'  # ✅ Necessário para UserSerializer
            ).prefetch_related(
                'attachments',
                'sender__departments'  # ✅ Necessário para UserSerializer.get_department_ids
            ).get
        )(id=message_id)
        
        log.debug(
            "✅ Mensagem carregada | conversation=%s tenant=%s content_preview=%s",
            message.conversation.contact_phone,
            message.conversation.tenant.name,
            (message.content or '')[:50],
        )
        
        # Se for nota interna, não envia
        if message.is_internal:
            message.status = 'sent'
            await sync_to_async(message.save)(update_fields=['status'])
            log.info("📝 Nota interna criada (não enviada ao WhatsApp)")
            return
        
        # Busca instância WhatsApp ativa do tenant (mesmo modelo das campanhas)
        log.debug("🔍 Buscando instância WhatsApp ativa...")
        
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
            log.error("❌ Nenhuma instância WhatsApp ativa | tenant=%s", message.conversation.tenant.name)
            return
        
        log.debug(
            "✅ Instância ativa | nome=%s uuid=%s api_url=%s",
            instance.friendly_name,
            instance.instance_name,
            instance.api_url,
        )

        defer, state_info = should_defer_instance(instance.instance_name)
        if defer:
            wait_seconds = compute_backoff(retry_count)
            log.warning(
                "⏳ [CHAT ENVIO] Instância %s em estado %s (age=%.2fs). Reagendando em %ss.",
                instance.instance_name,
                (state_info.state if state_info else 'unknown'),
                (state_info.age if state_info else -1),
                wait_seconds,
            )
            raise InstanceTemporarilyUnavailable(instance.instance_name, (state_info.raw if state_info else {}), wait_seconds)

        if instance.connection_state and instance.connection_state not in ('open', 'connected', 'active'):
            wait_seconds = compute_backoff(retry_count)
            log.warning(
                "⏳ [CHAT ENVIO] connection_state=%s. Reagendando em %ss.",
                instance.connection_state,
                wait_seconds,
            )
            raise InstanceTemporarilyUnavailable(instance.instance_name, {'state': instance.connection_state}, wait_seconds)
        
        # Prepara dados
        conversation = message.conversation
        
        def get_recipient():
            """Retorna tuple (field, value) conforme tipo da conversa."""
            if conversation.conversation_type == 'group':
                group_id = (conversation.group_metadata or {}).get('group_id') or conversation.contact_phone
                group_id = (group_id or '').strip()
                if group_id.endswith('@s.whatsapp.net'):
                    group_id = group_id.replace('@s.whatsapp.net', '@g.us')
                return 'groupId', group_id
            # individuais
            phone_number = (conversation.contact_phone or '').strip()
            phone_number = phone_number.replace('@s.whatsapp.net', '')
            if not phone_number.startswith('+'):
                phone_number = f'+{phone_number.lstrip("+")}'
            return 'number', phone_number

        recipient_field, recipient_value = get_recipient()
        phone = recipient_value
        
        content = message.content
        attachment_urls = message.metadata.get('attachment_urls', []) if message.metadata else []
        include_signature = message.metadata.get('include_signature', True) if message.metadata else True  # ✅ Por padrão inclui assinatura
        
        # ✍️ ASSINATURA AUTOMÁTICA: Adicionar nome do usuário no início da mensagem
        # Formato: *Nome Sobrenome:*\n\n{mensagem}
        # ✅ Só adiciona se include_signature=True no metadata
        if include_signature:
            sender = message.sender  # ✅ Já carregado via select_related
            if sender and content:
                first_name = sender.first_name or ''
                last_name = sender.last_name or ''
                
                if first_name or last_name:
                    # Montar assinatura com nome completo em negrito
                    full_name = f"{first_name} {last_name}".strip()
                    signature = f"*{full_name}:*\n\n"
                    content = signature + content
                    logger.info(f"✍️ [CHAT ENVIO] Assinatura adicionada: {full_name}")
        else:
            logger.info(f"✍️ [CHAT ENVIO] Assinatura desabilitada pelo usuário")
        
        logger.info("📱 [CHAT ENVIO] Destino=%s | tipo=%s", phone, conversation.conversation_type)
        
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
            
            # ✅ USAR API KEY GLOBAL (do .env) ao invés da instância
            # Ref: 403 Forbidden em sendWhatsAppAudio pode exigir API key global
            from django.conf import settings
            global_api_key = getattr(settings, 'EVOLUTION_API_KEY', '') or instance.api_key
            
            headers = {
                'apikey': global_api_key,
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔑 [CHAT] API Key: {'GLOBAL (settings)' if global_api_key != instance.api_key else 'INSTANCE'}")
            
            # Se tiver anexos, envia cada um
            if attachment_urls:
                for idx, url in enumerate(attachment_urls):
                    # Detectar mediatype e filename baseado no attachment
                    mime_type = 'application/pdf'  # default
                    filename = 'file'
                    attachment_obj = None
                    
                    if attachments_list and idx < len(attachments_list):
                        attachment_obj = attachments_list[idx]
                        mime_type = attachment_obj.mime_type
                        filename = attachment_obj.original_filename
                    
                    # ✅ USAR SHORT_URL se disponível (evita URLs longas do S3)
                    # URLs longas causam 403 na Evolution API
                    if attachment_obj and attachment_obj.short_url:
                        final_url = attachment_obj.short_url
                        logger.info(f"🔗 [CHAT] Usando URL curta: {final_url}")
                    else:
                        final_url = url  # Fallback para presigned URL
                        logger.warning(f"⚠️ [CHAT] short_url não disponível, usando presigned URL (pode falhar!)")
                    
                    # Mapear mime_type para mediatype da Evolution API
                    is_audio = mime_type.startswith('audio/')
                    
                    # 🎤 ÁUDIO: Usar sendWhatsAppAudio (confirmado que existe e retorna ptt:true)
                    if is_audio:
                        # Estrutura para PTT via sendWhatsAppAudio
                        # Ref: https://doc.evolution-api.com/v2/api-reference/message-controller/send-audio
                        # TESTADO E FUNCIONANDO: {number, audio, delay, linkPreview: false}
                        # ✅ CACHE STRATEGY: Redis 7 dias + S3 30 dias via /media/{hash}
                        payload = {
                            recipient_field: recipient_value,
                            'audio': final_url,   # URL CURTA! (/media/{hash})
                            'delay': 1200,        # Delay opcional
                            'linkPreview': False  # ✅ OBRIGATÓRIO: evita "Encaminhada"
                        }
                        
                        logger.info("🎤 [CHAT] Enviando PTT via sendWhatsAppAudio")
                        logger.info("   Phone: %s", _mask_remote_jid(phone))
                        logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))
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
                        # ✅ USAR SHORT_URL (já configurado acima)
                        payload = {
                            recipient_field: recipient_value,
                            'media': final_url,      # URL CURTA! (/media/{hash})
                            'mediatype': mediatype,  # lowercase!
                            'fileName': filename     # Nome do arquivo
                        }
                        if content:
                            payload['caption'] = content  # Caption direto no root também
                    
                    # Endpoint: sendWhatsAppAudio para PTT, sendMedia para outros
                    if is_audio:
                        endpoint = f"{base_url}/message/sendWhatsAppAudio/{instance.instance_name}"
                        logger.info(f"🎯 [CHAT] Usando sendWhatsAppAudio (PTT)")
                    else:
                        endpoint = f"{base_url}/message/sendMedia/{instance.instance_name}"
                        logger.info("📎 [CHAT] Usando sendMedia (outros anexos)")

                    logger.info("🔍 [CHAT] Enviando mídia para Evolution API:")
                    logger.info("   Endpoint: %s", endpoint)
                    logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))

                    try:
                        response = await client.post(
                            endpoint,
                            headers=headers,
                            json=payload
                        )
                        logger.info(f"📥 [CHAT] Resposta Evolution API:")
                        logger.info(f"   Status: {response.status_code}")
                        logger.info(f"   Body completo: {response.text}")
                        response.raise_for_status()
                    except httpx.HTTPStatusError as e:
                        # Fallback: algumas instalações não expõem sendWhatsAppAudio; tentar sendMedia com mediatype=audio
                        if is_audio and e.response is not None and e.response.status_code == 404:
                            fb_endpoint = f"{base_url}/message/sendMedia/{instance.instance_name}"
                            fb_payload = {
                                recipient_field: recipient_value,
                                'media': final_url,
                                'mediatype': 'audio',
                                'fileName': filename,
                                'linkPreview': False
                            }
                            logger.warning("⚠️ [CHAT] sendWhatsAppAudio retornou 404. Tentando fallback sendMedia (audio)...")
                            logger.info(f"   FB Endpoint: {fb_endpoint}")
                            logger.info(f"   FB Payload: {json.dumps(fb_payload)}")
                            fb_resp = await client.post(
                                fb_endpoint,
                                headers=headers,
                                json=fb_payload
                            )
                            logger.info("📥 [CHAT] Resposta Evolution API (fallback): %s", fb_resp.status_code)
                            try:
                                fb_json = fb_resp.json()
                            except ValueError:
                                fb_json = None
                            if fb_json is not None:
                                logger.info("   Body (mascado): %s", mask_sensitive_data(fb_json))
                            else:
                                logger.info("   Body (texto): %s", _truncate_text(fb_resp.text))
                            fb_resp.raise_for_status()
                            response = fb_resp
                        else:
                            raise
                    
                    try:
                        data = response.json()
                    except ValueError:
                        data = {}
                        logger.warning("⚠️ [CHAT] Resposta Evolution API sem JSON. Texto: %s", _truncate_text(response.text))

                    if data:
                        logger.info("📥 [CHAT] Resposta Evolution API: status=%s body=%s", response.status_code, mask_sensitive_data(data))
                    else:
                        logger.info("📥 [CHAT] Resposta Evolution API: status=%s body=%s", response.status_code, _truncate_text(response.text))
                    evolution_message_id = data.get('key', {}).get('id')
                    
                    # ✅ FIX CRÍTICO: Salvar message_id IMEDIATAMENTE para evitar race condition
                    if evolution_message_id:
                        message.message_id = evolution_message_id
                        # ✅ Salvar message_id ANTES de continuar
                        await sync_to_async(message.save)(update_fields=['message_id'])
                        logger.info(f"💾 [CHAT] Message ID salvo IMEDIATAMENTE: {evolution_message_id}")
                    
                    logger.info(f"✅ [CHAT] Mídia enviada: {message_id}")
                    await asyncio.sleep(0.2)
            
            # Envia texto (se não tiver anexo ou como caption separado)
            if content and not attachment_urls:
                # 🔍 PARA GRUPOS: não formatar (já vem como "120363...@g.us")
                # Para contatos individuais: adicionar + se não tiver
                payload = {
                    recipient_field: recipient_value,
                    'text': content,
                    'instance': instance.instance_name
                }
                
                logger.info(f"📤 [CHAT ENVIO] Enviando mensagem de texto para Evolution API...")
                logger.info(f"   Tipo: {conversation.conversation_type}")
                logger.info(f"   URL: {base_url}/message/sendText/{instance.instance_name}")
                logger.info("   Phone original: %s", _mask_remote_jid(phone))
                logger.info("   Phone formatado: %s", _mask_remote_jid(formatted_phone))
                logger.info("   Text: %s", _truncate_text(content))
                logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))
                
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
                evolution_message_id = data.get('key', {}).get('id')
                
                # ✅ FIX CRÍTICO: Salvar message_id IMEDIATAMENTE para evitar race condition
                # O webhook pode chegar muito rápido (antes do save completo)
                if evolution_message_id:
                    message.message_id = evolution_message_id
                    # ✅ Salvar message_id ANTES de salvar status completo
                    # Isso garante que webhook encontra a mensagem mesmo se chegar muito rápido
                    await sync_to_async(message.save)(update_fields=['message_id'])
                    logger.info(f"💾 [CHAT ENVIO] Message ID salvo IMEDIATAMENTE: {evolution_message_id}")
                
                logger.info(f"✅ [CHAT ENVIO] Mensagem enviada com sucesso!")
                logger.info(f"   Message ID Evolution: {message.message_id}")
        
        # Atualiza status (message_id já foi salvo acima se disponível)
        message.status = 'sent'
        message.evolution_status = 'sent'
        # ✅ Atualizar apenas status/evolution_status (message_id já foi salvo)
        await sync_to_async(message.save)(update_fields=['status', 'evolution_status'])
        
        logger.info(f"💾 [CHAT ENVIO] Status atualizado no banco para 'sent'")
        
        # ✅ FIX CRÍTICO: Broadcast via WebSocket para adicionar mensagem em tempo real
        # Enviar TANTO message_received (para adicionar mensagem) QUANTO message_status_update (para atualizar status)
        logger.info(f"📡 [CHAT ENVIO] Preparando broadcast via WebSocket...")
        
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
        tenant_group = f"chat_tenant_{message.conversation.tenant_id}"
        
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Tenant Group: {tenant_group}")
        
        from apps.chat.utils.serialization import serialize_message_for_ws, serialize_conversation_for_ws
        
        # ✅ Usar database_sync_to_async para serialização (MessageSerializer acessa relacionamentos do DB)
        message_data_serializable = await database_sync_to_async(serialize_message_for_ws)(message)
        conversation_data_serializable = await database_sync_to_async(serialize_conversation_for_ws)(message.conversation)
        
        # ✅ FIX: Enviar message_received para adicionar mensagem em tempo real (TANTO na room QUANTO no tenant)
        # Isso garante que a mensagem apareça imediatamente na conversa ativa
        await channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data_serializable
            }
        )
        
        await channel_layer.group_send(
            tenant_group,
            {
                'type': 'message_received',
                'message': message_data_serializable,
                'conversation': conversation_data_serializable
            }
        )
        
        # ✅ Também enviar message_status_update para atualizar status
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
        logger.info(f"   Broadcast: message_received + message_status_update")
    
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro ao enviar mensagem {message_id}: {e}", exc_info=True)
        
        # Marca como falha
        try:
            message.status = 'failed'
            message.error_message = str(e)
            await sync_to_async(message.save)(update_fields=['status', 'error_message'])
        except:
            pass


# ❌ handle_download_attachment e handle_migrate_s3 REMOVIDOS
# Motivo: Fluxo antigo de 2 etapas substituído por process_incoming_media
# que faz download direto para S3 + cache Redis em uma única etapa


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
                        from apps.chat.utils.serialization import serialize_conversation_for_ws
                        
                        conv_data_serializable = serialize_conversation_for_ws(conversation)
                        
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


async def handle_mark_message_as_read(conversation_id: str, message_id: str, retry_count: int = 0):
    """
    Handler: Envia read receipt para mensagens em background.
    """
    from apps.chat.models import Message
    from asgiref.sync import sync_to_async

    try:
        message = await sync_to_async(
            Message.objects.select_related('conversation', 'conversation__tenant').get
        )(id=message_id, conversation_id=conversation_id)
    except Message.DoesNotExist:
        read_logger.warning(
            "⚠️ [READ RECEIPT WORKER] Mensagem não encontrada (message_id=%s, conversation_id=%s)",
            message_id,
            conversation_id
        )
        return

    if not message.message_id:
        read_logger.warning(
            "⚠️ [READ RECEIPT WORKER] Mensagem sem message_id da Evolution, pulando (message_id=%s)",
            message_id
        )
        return

    read_logger.info(
        "📖 [READ RECEIPT] Processando message=%s conversation=%s",
        message_id,
        conversation_id,
    )

    # Garantir status 'seen' no banco (caso ainda não atualizado)
    if message.status != 'seen':
        await sync_to_async(
            Message.objects.filter(id=message.id).update
        )(status='seen')
        message.status = 'seen'

    from apps.notifications.models import WhatsAppInstance

    wa_instance = await sync_to_async(
        WhatsAppInstance.objects.filter(
            tenant=message.conversation.tenant,
            is_active=True
        ).first
    )()

    if wa_instance:
        defer, state_info = should_defer_instance(wa_instance.instance_name)
        if defer:
            wait_seconds = compute_backoff(retry_count)
            read_logger.warning(
                "⏳ [READ RECEIPT] Instância %s em estado %s (age=%.2fs). Reagendando em %ss.",
                wa_instance.instance_name,
                (state_info.state if state_info else 'unknown'),
                (state_info.age if state_info else -1),
                wait_seconds,
            )
            raise InstanceTemporarilyUnavailable(wa_instance.instance_name, (state_info.raw if state_info else {}), wait_seconds)

        if wa_instance.connection_state and wa_instance.connection_state not in ('open', 'connected', 'active'):
            wait_seconds = compute_backoff(retry_count)
            read_logger.warning(
                "⏳ [READ RECEIPT] connection_state=%s no modelo. Reagendando em %ss.",
                wa_instance.connection_state,
                wait_seconds,
            )
            raise InstanceTemporarilyUnavailable(wa_instance.instance_name, {'state': wa_instance.connection_state}, wait_seconds)

    sent = await sync_to_async(send_read_receipt)(
        message.conversation,
        message,
        max_retries=2
    )

    if not sent:
        read_logger.warning(
            "⚠️ [READ RECEIPT WORKER] Read receipt não enviado (message_id=%s, conversation_id=%s)",
            message_id,
            conversation_id
        )


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
        queue_profile_pic = await channel.declare_queue(QUEUE_FETCH_PROFILE_PIC, durable=True)
        queue_process_incoming_media = await channel.declare_queue(QUEUE_PROCESS_INCOMING_MEDIA, durable=True)
        queue_fetch_group_info = await channel.declare_queue(QUEUE_FETCH_GROUP_INFO, durable=True)  # ✅ NOVO
        
        logger.info("✅ [CHAT CONSUMER] Filas declaradas")
        
        # Consumer: send_message
        async def on_send_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await handle_send_message(payload['message_id'])
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro send_message: {e}", exc_info=True)
        
        # ❌ Consumers download_attachment e migrate_to_s3 REMOVIDOS
        # Motivo: Fluxo antigo substituído por process_incoming_media
        
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
        
        # Consumer: process_incoming_media (novo fluxo: S3 direto - sem cache)
        async def on_process_incoming_media(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    from apps.chat.media_tasks import handle_process_incoming_media
                    payload = json.loads(message.body.decode())
                    logger.info(f"📥 [CHAT CONSUMER] Recebida task process_incoming_media")
                    logger.info(f"   📌 tenant_id: {payload.get('tenant_id')}")
                    logger.info(f"   📌 message_id: {payload.get('message_id')}")
                    logger.info(f"   📌 media_type: {payload.get('media_type')}")
                    logger.info(f"   📌 media_url: {payload.get('media_url', '')[:100]}...")
                    logger.info(f"   📌 instance_name: {payload.get('instance_name')}")
                    logger.info(f"   📌 api_key: {'Configurada' if payload.get('api_key') else 'Não configurada'}")
                    logger.info(f"   📌 evolution_api_url: {payload.get('evolution_api_url')}")
                    logger.info(f"   📌 message_key: {payload.get('message_key')}")
                    message_key_from_payload = payload.get('message_key')
                    if message_key_from_payload:
                        logger.info(f"   ✅ [CHAT CONSUMER] message_key recebido: id={message_key_from_payload.get('id')}, remoteJid={message_key_from_payload.get('remoteJid')}")
                    retry_count = payload.get('_retry_count', 0)
                    await handle_process_incoming_media(
                        tenant_id=payload['tenant_id'],
                        message_id=payload['message_id'],
                        media_url=payload['media_url'],
                        media_type=payload['media_type'],
                        instance_name=payload.get('instance_name'),
                        api_key=payload.get('api_key'),
                        evolution_api_url=payload.get('evolution_api_url'),
                        message_key=message_key_from_payload,
                        retry_count=retry_count,
                    )
                    logger.info(f"✅ [CHAT CONSUMER] process_incoming_media concluída com sucesso")
                except InstanceTemporarilyUnavailable as e:
                    wait_time = e.wait_seconds or compute_backoff(payload.get('_retry_count', 0))
                    next_retry = payload.get('_retry_count', 0) + 1
                    logger.warning(
                        "⏳ [CHAT CONSUMER] Instância indisponível para process_incoming_media (message=%s). Reagendando em %ss. Estado: %s",
                        payload.get('message_id'),
                        wait_time,
                        e.state_payload or {},
                    )
                    payload['_retry_count'] = next_retry
                    payload['_last_error'] = e.state_payload or {}
                    await asyncio.sleep(wait_time)
                    await queue_process_incoming_media.channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(payload).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=queue_process_incoming_media.name,
                    )
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro process_incoming_media: {e}", exc_info=True)
                    raise  # ✅ Re-raise para não silenciar erro
        
        # Consumer: fetch_group_info (✅ NOVO: busca informações de grupo de forma assíncrona)
        async def on_fetch_group_info(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    from apps.chat.media_tasks import handle_fetch_group_info
                    payload = json.loads(message.body.decode())
                    logger.info(f"📥 [CHAT CONSUMER] Recebida task fetch_group_info")
                    logger.info(f"   📌 conversation_id: {payload.get('conversation_id')}")
                    logger.info(f"   📌 group_jid: {payload.get('group_jid')}")
                    await handle_fetch_group_info(
                        conversation_id=payload['conversation_id'],
                        group_jid=payload['group_jid'],
                        instance_name=payload['instance_name'],
                        api_key=payload['api_key'],
                        base_url=payload['base_url']
                    )
                    logger.info(f"✅ [CHAT CONSUMER] fetch_group_info concluída com sucesso")
                except Exception as e:
                    logger.error(f"❌ [CHAT CONSUMER] Erro fetch_group_info: {e}", exc_info=True)
                    raise  # ✅ Re-raise para não silenciar erro
        
        # Inicia consumo
        await queue_send.consume(on_send_message)
        await queue_profile_pic.consume(on_fetch_profile_pic)
        await queue_process_incoming_media.consume(on_process_incoming_media)
        await queue_fetch_group_info.consume(on_fetch_group_info)  # ✅ NOVO
        
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

