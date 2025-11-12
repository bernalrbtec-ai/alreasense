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
import time
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import IntegrityError
from apps.chat.webhooks import send_read_receipt
from apps.chat.utils.instance_state import (
    should_defer_instance,
    InstanceTemporarilyUnavailable,
    compute_backoff,
)
from apps.chat.utils.metrics import record_latency, record_error

logger = logging.getLogger(__name__)
send_logger = logging.getLogger("flow.chat.send")
read_logger = logging.getLogger("flow.chat.read")


def extract_evolution_message_id(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Extrai o ID de mensagem retornado pela Evolution API.
    O webhook usa o campo `messageId`, então priorizamos esse valor.
    """
    if not data:
        return None

    messages = data.get('messages')
    first_message = messages[0] if isinstance(messages, list) and messages else {}

    return (
        data.get('messageId')
        or data.get('id')
        or first_message.get('messageId')
        or first_message.get('id')
        or first_message.get('key', {}).get('id')
        or data.get('key', {}).get('id')
    )


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
    REDIS_QUEUE_FETCH_PROFILE_PIC,
    REDIS_QUEUE_FETCH_GROUP_INFO,
    REDIS_QUEUE_FETCH_CONTACT_NAME,  # ✅ NOVO: Busca nome de contato
)
from apps.chat.redis_streams import (
    enqueue_send_message as enqueue_send_stream_message,
    enqueue_mark_as_read as enqueue_mark_stream_message,
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
        enqueue_send_stream_message(message_id)


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


class fetch_contact_name:
    """Producer: Busca nome de contato via Evolution API (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(conversation_id: str, phone: str, instance_name: str, api_key: str, base_url: str):
        """Enfileira busca de nome de contato (Redis)."""
        enqueue_message(REDIS_QUEUE_FETCH_CONTACT_NAME, {
            'conversation_id': conversation_id,
            'phone': phone,
            'instance_name': instance_name,
            'api_key': api_key,
            'base_url': base_url
        })


def enqueue_mark_as_read(conversation_id: str, message_id: str):
    """Producer auxiliar: enfileira envio de read receipt."""
    enqueue_mark_stream_message(conversation_id, message_id)


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

    overall_start = time.perf_counter()

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
        
        # Helper para tratar message_id duplicado
        async def handle_duplicate_message_id(evolution_message_id: str):
            metadata = message.metadata or {}
            metadata['duplicate_message_id'] = evolution_message_id
            existing_message = await sync_to_async(
                Message.objects.filter(message_id=evolution_message_id).exclude(id=message.id).first
            )()
            if existing_message:
                metadata['duplicate_of'] = str(existing_message.id)
                new_status = existing_message.status
                new_evolution_status = existing_message.evolution_status
            else:
                new_status = 'sent'
                new_evolution_status = 'sent'
            await sync_to_async(
                Message.objects.filter(id=message.id).update
            )(
                status=new_status,
                evolution_status=new_evolution_status,
                message_id=None,
                metadata=metadata,
            )
            message.status = new_status
            message.evolution_status = new_evolution_status
            message.message_id = None
            message.metadata = metadata

        # Prepara dados
        conversation = message.conversation
        
        def get_recipient():
            """Retorna número formatado (E.164 ou group jid) e versão mascarada."""
            if conversation.conversation_type == 'group':
                group_id = (conversation.group_metadata or {}).get('group_id') or conversation.contact_phone
                group_id = (group_id or '').strip()
                if group_id.endswith('@s.whatsapp.net'):
                    group_id = group_id.replace('@s.whatsapp.net', '@g.us')
                if not group_id.endswith('@g.us'):
                    group_id = f"{group_id.rstrip('@')}@g.us"
                return group_id, _mask_remote_jid(group_id)
            # individuais
            phone_number = (conversation.contact_phone or '').strip()
            phone_number = phone_number.replace('@s.whatsapp.net', '')
            if not phone_number.startswith('+'):
                phone_number = f'+{phone_number.lstrip("+")}'
            return phone_number, _mask_remote_jid(phone_number)

        recipient_value, masked_recipient = get_recipient()
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
                            'number': recipient_value,
                            'audio': final_url,   # URL CURTA! (/media/{hash})
                            'delay': 1200,        # Delay opcional
                            'linkPreview': False  # ✅ OBRIGATÓRIO: evita "Encaminhada"
                        }
                        
                        logger.info("🎤 [CHAT] Enviando PTT via sendWhatsAppAudio")
                        logger.info("   Destinatário: %s", masked_recipient)
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
                            'number': recipient_value,
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
                    logger.info("   Destinatário: %s", masked_recipient)
                    logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))

                    try:
                        request_start = time.perf_counter()
                        response = await client.post(
                            endpoint,
                            headers=headers,
                            json=payload
                        )
                        latency = time.perf_counter() - request_start
                        record_latency(
                            'send_message_media',
                            latency,
                            {
                                'message_id': str(message.id),
                                'conversation_id': str(conversation.id),
                                'mediatype': 'audio' if is_audio else mediatype,
                                'status_code': response.status_code,
                            }
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
                                'number': recipient_value,
                                'media': final_url,
                                'mediatype': 'audio',
                                'fileName': filename,
                                'linkPreview': False
                            }
                            logger.warning("⚠️ [CHAT] sendWhatsAppAudio retornou 404. Tentando fallback sendMedia (audio)...")
                            logger.info(f"   FB Endpoint: {fb_endpoint}")
                            logger.info(f"   FB Payload: {json.dumps(fb_payload)}")
                            request_start = time.perf_counter()
                            fb_resp = await client.post(
                                fb_endpoint,
                                headers=headers,
                                json=fb_payload
                            )
                            latency = time.perf_counter() - request_start
                            record_latency(
                                'send_message_media',
                                latency,
                                {
                                    'message_id': str(message.id),
                                    'conversation_id': str(conversation.id),
                                    'mediatype': 'audio',
                                    'fallback': True,
                                    'status_code': fb_resp.status_code,
                                }
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
                    evolution_message_id = extract_evolution_message_id(data)
                    
                    # ✅ FIX CRÍTICO: Salvar message_id IMEDIATAMENTE para evitar race condition
                    if evolution_message_id:
                        message.message_id = evolution_message_id
                        try:
                            # ✅ Salvar message_id ANTES de continuar
                            await sync_to_async(message.save)(update_fields=['message_id'])
                            logger.info(f"💾 [CHAT] Message ID salvo IMEDIATAMENTE: {evolution_message_id}")
                        except IntegrityError:
                            logger.warning(
                                "⚠️ [CHAT] message_id duplicado (%s). Reutilizando mensagem existente.",
                                evolution_message_id
                            )
                            await handle_duplicate_message_id(evolution_message_id)
                    
                    logger.info(f"✅ [CHAT] Mídia enviada: {message_id}")
            
            # Envia texto (se não tiver anexo ou como caption separado)
            if content and not attachment_urls:
                # 🔍 PARA GRUPOS: não formatar (já vem como "120363...@g.us")
                # Para contatos individuais: adicionar + se não tiver
                # ✅ CORREÇÃO: Remover campo 'instance' do payload (já está na URL)
                payload = {
                    'number': recipient_value,
                    'text': content
                }
                
                logger.info(f"📤 [CHAT ENVIO] Enviando mensagem de texto para Evolution API...")
                logger.info(f"   Tipo: {conversation.conversation_type}")
                logger.info(f"   URL: {base_url}/message/sendText/{instance.instance_name}")
                logger.info("   Destinatário: %s", masked_recipient)
                logger.info("   Text: %s", _truncate_text(content))
                logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))
                
                request_start = time.perf_counter()
                response = await client.post(
                    f"{base_url}/message/sendText/{instance.instance_name}",
                    headers=headers,
                    json=payload
                )
                latency = time.perf_counter() - request_start
                record_latency(
                    'send_message_text',
                    latency,
                    {
                        'message_id': str(message.id),
                        'conversation_id': str(conversation.id),
                        'has_attachments': bool(attachment_urls),
                        'status_code': response.status_code,
                    }
                )
                
                logger.info(f"📥 [CHAT ENVIO] Resposta da Evolution API:")
                logger.info(f"   Status: {response.status_code}")
                logger.info(f"   Body: {response.text[:300]}")
                
                response.raise_for_status()
                
                data = response.json()
                evolution_message_id = extract_evolution_message_id(data)
                
                # ✅ FIX CRÍTICO: Salvar message_id IMEDIATAMENTE para evitar race condition
                # O webhook pode chegar muito rápido (antes do save completo)
                if evolution_message_id:
                    message.message_id = evolution_message_id
                    try:
                        # ✅ Salvar message_id ANTES de salvar status completo
                        # Isso garante que webhook encontra a mensagem mesmo se chegar muito rápido
                        await sync_to_async(message.save)(update_fields=['message_id'])
                        logger.info(f"💾 [CHAT ENVIO] Message ID salvo IMEDIATAMENTE: {evolution_message_id}")
                    except IntegrityError:
                        logger.warning(
                            "⚠️ [CHAT] message_id duplicado (%s) ao enviar texto. Reutilizando mensagem existente.",
                            evolution_message_id
                        )
                        await handle_duplicate_message_id(evolution_message_id)
                
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

        record_latency(
            'send_message_total',
            time.perf_counter() - overall_start,
            {
                'message_id': str(message.id),
                'conversation_id': str(conversation.id),
                'attachments': len(attachment_urls),
            }
        )
    
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro ao enviar mensagem {message_id}: {e}", exc_info=True)
        record_error('send_message', str(e))
        
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


def _format_phone_for_display(phone: str) -> str:
    """
    Formata telefone para exibição (como WhatsApp faz).
    
    Exemplos:
    - +5511999999999 → (11) 99999-9999
    - 5511999999999 → (11) 99999-9999
    - 11999999999 → (11) 99999-9999
    
    Args:
        phone: Telefone em qualquer formato
    
    Returns:
        Telefone formatado para exibição
    """
    import re
    
    # Remover caracteres não numéricos
    clean = re.sub(r'\D', '', phone)
    
    # Se começar com 55 (código do Brasil), remover
    if clean.startswith('55') and len(clean) >= 12:
        clean = clean[2:]
    
    # Formatar: (XX) XXXXX-XXXX para celular ou (XX) XXXX-XXXX para fixo
    if len(clean) == 11:  # Celular com DDD
        return f"({clean[0:2]}) {clean[2:7]}-{clean[7:11]}"
    elif len(clean) == 10:  # Fixo com DDD
        return f"({clean[0:2]}) {clean[2:6]}-{clean[6:10]}"
    elif len(clean) == 9:  # Celular sem DDD
        return f"{clean[0:5]}-{clean[5:9]}"
    elif len(clean) == 8:  # Fixo sem DDD
        return f"{clean[0:4]}-{clean[4:8]}"
    else:
        # Se não conseguir formatar, retornar como está (limitado a 15 chars)
        return clean[:15] if clean else phone


async def handle_fetch_profile_pic(conversation_id: str, phone: str):
    """
    Handler: Busca foto de perfil via Evolution API e salva.
    
    ✅ MELHORIA: Também busca nome do contato se não tiver ou estiver incorreto.
    
    Fluxo:
    1. Busca conversa e instância Evolution
    2. Chama endpoint /chat/fetchProfilePictureUrl
    3. Se retornar URL, salva no campo profile_pic_url
    4. ✅ NOVO: Busca nome do contato também
    5. Broadcast atualização via WebSocket
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
        clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
        
        # Endpoint Evolution API
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        update_fields = []
        
        # ✅ MELHORIA: Retry com backoff exponencial para erros de rede (similar a grupos)
        # 1️⃣ Buscar foto de perfil (com retry)
        max_retries = 3
        retry_count = 0
        photo_fetched = False
        
        while retry_count < max_retries and not photo_fetched:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance_name}"
                    
                    logger.info(f"📡 [PROFILE PIC] Chamando Evolution API (tentativa {retry_count + 1}/{max_retries})...")
                    logger.info(f"   Endpoint: {endpoint}")
                    logger.info(f"   Phone (clean): {clean_phone}")
                    
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
                            
                            conversation.profile_pic_url = profile_url
                            update_fields.append('profile_pic_url')
                            photo_fetched = True
                        else:
                            logger.info(f"ℹ️ [PROFILE PIC] Foto não disponível na API")
                            photo_fetched = True  # Não é erro, só não tem foto
                    elif response.status_code == 404:
                        logger.info(f"ℹ️ [PROFILE PIC] Foto não encontrada (404) - contato pode não ter foto")
                        photo_fetched = True  # Não é erro, só não tem foto
                    else:
                        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                        
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Backoff exponencial: 2s, 4s, 8s
                    logger.warning(f"⚠️ [PROFILE PIC] Timeout/erro de conexão (tentativa {retry_count}/{max_retries}): {e}")
                    logger.info(f"⏳ [PROFILE PIC] Aguardando {wait_time}s antes de tentar novamente...")
                    import asyncio
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ [PROFILE PIC] Falha após {max_retries} tentativas: {e}")
            except Exception as e:
                logger.error(f"❌ [PROFILE PIC] Erro inesperado ao buscar foto: {e}", exc_info=True)
                photo_fetched = True  # Parar retry para erros não relacionados a rede
        
        # 2️⃣ Buscar nome do contato (sempre executar, mesmo se foto falhou)
        async with httpx.AsyncClient(timeout=10.0) as client:
            
            # 2️⃣ ✅ MELHORIA: Sempre buscar e atualizar nome do contato (garante nome correto)
            # Mesmo se já existir um nome, atualizar para garantir que está correto
            logger.info(f"👤 [PROFILE PIC] Buscando nome do contato...")
            endpoint_name = f"{base_url}/chat/whatsappNumbers/{instance_name}"
            
            try:
                # ✅ Aumentar timeout para buscar nome (pode ser mais tolerante que foto)
                response_name = await client.post(
                    endpoint_name,
                    json={'numbers': [clean_phone]},
                    headers=headers,
                    timeout=15.0  # ✅ Aumentado de 10s para 15s (mais tolerante)
                )
                
                logger.info(f"📥 [PROFILE PIC] Nome response status: {response_name.status_code}")
                
                if response_name.status_code == 200:
                    data_name = response_name.json()
                    logger.info(f"📦 [PROFILE PIC] Nome response data: {data_name}")
                    
                    # Resposta: [{"jid": "...", "exists": true, "name": "..."}]
                    if data_name and len(data_name) > 0:
                        contact_info = data_name[0]
                        contact_name = contact_info.get('name') or contact_info.get('pushname', '')
                        
                        logger.info(f"🔍 [PROFILE PIC] Nome extraído: '{contact_name}' (exists: {contact_info.get('exists', False)})")
                        
                        if contact_name and contact_name.strip():
                            # ✅ MELHORIA: Sempre atualizar nome, mesmo se já existir (garante nome correto)
                            old_name = conversation.contact_name
                            conversation.contact_name = contact_name.strip()
                            update_fields.append('contact_name')
                            logger.info(f"✅ [PROFILE PIC] Nome atualizado: '{old_name}' → '{contact_name.strip()}'")
                        else:
                            logger.warning(f"⚠️ [PROFILE PIC] Nome vazio ou não disponível na API")
                            logger.warning(f"   Response: {contact_info}")
                            # ✅ FALLBACK: Sempre usar telefone formatado se não tiver nome (como WhatsApp)
                            formatted_phone = _format_phone_for_display(clean_phone)
                            if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp' or conversation.contact_name == clean_phone:
                                conversation.contact_name = formatted_phone
                                update_fields.append('contact_name')
                                logger.info(f"ℹ️ [PROFILE PIC] Usando telefone formatado como nome: {formatted_phone}")
                    else:
                        logger.warning(f"⚠️ [PROFILE PIC] Resposta vazia ou inválida da API de nomes")
                        logger.warning(f"   Response: {data_name}")
                else:
                    logger.error(f"❌ [PROFILE PIC] Erro HTTP ao buscar nome: {response_name.status_code}")
                    logger.error(f"   Response text: {response_name.text[:200]}")
                    # ✅ FALLBACK: Se erro HTTP, usar telefone formatado
                    if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                        formatted_phone = _format_phone_for_display(clean_phone)
                        conversation.contact_name = formatted_phone
                        update_fields.append('contact_name')
                        logger.info(f"ℹ️ [PROFILE PIC] Erro HTTP, usando telefone formatado: {formatted_phone}")
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
                # ✅ Erros de rede/timeout - logar sem traceback completo (erro esperado)
                logger.warning(f"⚠️ [PROFILE PIC] Timeout/erro de conexão ao buscar nome: {type(e).__name__}")
                logger.warning(f"   Endpoint: {endpoint_name}")
                logger.warning(f"   Telefone: {clean_phone}")
                # ✅ FALLBACK: Se erro de rede, usar telefone formatado
                if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                    formatted_phone = _format_phone_for_display(clean_phone)
                    conversation.contact_name = formatted_phone
                    update_fields.append('contact_name')
                    logger.info(f"ℹ️ [PROFILE PIC] Erro de rede, usando telefone formatado: {formatted_phone}")
            except Exception as e:
                # ✅ Outros erros - logar com traceback (erro inesperado)
                logger.error(f"❌ [PROFILE PIC] Erro inesperado ao buscar nome: {type(e).__name__}: {e}", exc_info=True)
                # ✅ FALLBACK: Se erro ao buscar nome, garantir que tenha telefone formatado
                if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                    formatted_phone = _format_phone_for_display(clean_phone)
                    conversation.contact_name = formatted_phone
                    update_fields.append('contact_name')
                    logger.info(f"ℹ️ [PROFILE PIC] Erro ao buscar nome, usando telefone formatado: {formatted_phone}")
            
            # ✅ GARANTIR: Se ainda não tem nome após todas as tentativas, usar telefone formatado
            if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                formatted_phone = _format_phone_for_display(clean_phone)
                conversation.contact_name = formatted_phone
                update_fields.append('contact_name')
                logger.info(f"ℹ️ [PROFILE PIC] Garantindo telefone formatado como nome: {formatted_phone}")
            
            # Salvar atualizações
            if update_fields:
                await sync_to_async(conversation.save)(update_fields=update_fields)
                logger.info(f"✅ [PROFILE PIC] Atualizações salvas: {', '.join(update_fields)}")
                
                # ✅ CRÍTICO: Sempre fazer broadcast se houver atualizações (foto OU nome)
                # Isso garante que o frontend recebe atualizações mesmo se só o nome mudou
                try:
                    from apps.chat.utils.serialization import serialize_conversation_for_ws_async
                    
                    # ✅ IMPORTANTE: Recarregar conversa do banco para garantir dados atualizados
                    await sync_to_async(conversation.refresh_from_db)()
                    conv_data_serializable = await serialize_conversation_for_ws_async(conversation)
                    
                    channel_layer = get_channel_layer()
                    tenant_group = f"chat_tenant_{conversation.tenant_id}"
                    
                    await channel_layer.group_send(
                        tenant_group,
                        {
                            'type': 'conversation_updated',
                            'conversation': conv_data_serializable
                        }
                    )
                    
                    logger.info(f"📡 [PROFILE PIC] Atualização broadcast via WebSocket (campos: {', '.join(update_fields)})")
                except Exception as e:
                    logger.error(f"❌ [PROFILE PIC] Erro no broadcast: {e}", exc_info=True)
            else:
                logger.info(f"ℹ️ [PROFILE PIC] Nenhuma atualização necessária")
    
    except Exception as e:
        logger.error(f"❌ [PROFILE PIC] Erro ao buscar foto: {e}", exc_info=True)


async def handle_fetch_contact_name(
    conversation_id: str, 
    phone: str, 
    instance_name: str, 
    api_key: str, 
    base_url: str
):
    """
    Handler: Busca nome de contato via Evolution API.
    
    ✅ NOVO: Task assíncrona dedicada para buscar nome de contato.
    
    Fluxo:
    1. Busca conversa
    2. Chama endpoint /chat/whatsappNumbers
    3. Atualiza contact_name
    4. Broadcast via WebSocket
    """
    from apps.chat.models import Conversation
    from channels.layers import get_channel_layer
    from asgiref.sync import sync_to_async
    import httpx
    
    logger.info(f"👤 [CONTACT NAME] Buscando nome de contato...")
    logger.info(f"   Conversation ID: {conversation_id}")
    logger.info(f"   Phone: {phone}")
    
    try:
        # Busca conversa
        conversation = await sync_to_async(
            Conversation.objects.select_related('tenant').get
        )(id=conversation_id)
        
        # Formatar telefone (sem + e sem @s.whatsapp.net)
        clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
        
        # Endpoint Evolution API
        endpoint = f"{base_url.rstrip('/')}/chat/whatsappNumbers/{instance_name}"
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"📡 [CONTACT NAME] Chamando Evolution API...")
        logger.info(f"   Endpoint: {endpoint}")
        logger.info(f"   Phone (clean): {clean_phone}")
        
        # ✅ MELHORIA: Retry com backoff exponencial para erros de rede
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        endpoint,
                        json={'numbers': [clean_phone]},
                        headers=headers
                    )
                    
                    logger.info(f"📥 [CONTACT NAME] Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Resposta: [{"jid": "...", "exists": true, "name": "..."}]
                        if data and len(data) > 0:
                            contact_info = data[0]
                            contact_name = contact_info.get('name') or contact_info.get('pushname', '')
                            
                            if contact_name:
                                # ✅ MELHORIA: Sempre atualizar nome, mesmo se já existir (garante nome correto)
                                old_name = conversation.contact_name
                                conversation.contact_name = contact_name
                                await sync_to_async(conversation.save)(update_fields=['contact_name'])
                                
                                logger.info(f"✅ [CONTACT NAME] Nome atualizado: '{old_name}' → '{contact_name}'")
                                
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
                                    
                                    logger.info(f"📡 [CONTACT NAME] Atualização broadcast via WebSocket")
                                except Exception as e:
                                    logger.error(f"❌ [CONTACT NAME] Erro no broadcast: {e}")
                            else:
                                logger.warning(f"⚠️ [CONTACT NAME] Nome não disponível na API")
                                # Fallback: usar telefone se não tiver nome
                                if not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                                    conversation.contact_name = clean_phone
                                    await sync_to_async(conversation.save)(update_fields=['contact_name'])
                                    logger.info(f"ℹ️ [CONTACT NAME] Usando telefone como nome")
                        else:
                            logger.warning(f"⚠️ [CONTACT NAME] Response vazio ou inválido")
                        
                        # ✅ Sucesso, sair do loop de retry
                        return
                    
                    elif response.status_code >= 500:
                        # Erro do servidor - pode tentar novamente
                        retry_count += 1
                        logger.warning(f"⚠️ [CONTACT NAME] Erro do servidor (tentativa {retry_count}/{max_retries}): HTTP {response.status_code}")
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count  # Backoff exponencial: 2s, 4s, 8s
                            logger.info(f"⏳ [CONTACT NAME] Aguardando {wait_time}s antes de retry...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"❌ [CONTACT NAME] Falhou após {max_retries} tentativas")
                            return
                    else:
                        # Outros erros HTTP (400, 401, 403, 404) - não retry
                        logger.warning(f"⚠️ [CONTACT NAME] Erro HTTP {response.status_code}: {response.text[:200]}")
                        return
                        
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
                # ✅ Erros de rede/conexão - fazer retry
                retry_count += 1
                logger.warning(f"⚠️ [CONTACT NAME] Erro de rede (tentativa {retry_count}/{max_retries}): {e}")
                
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Backoff exponencial: 2s, 4s, 8s
                    logger.info(f"⏳ [CONTACT NAME] Aguardando {wait_time}s antes de retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ [CONTACT NAME] Falhou após {max_retries} tentativas: {e}")
                    return
            
            except httpx.HTTPStatusError as e:
                # ✅ Erros HTTP específicos
                logger.warning(f"⚠️ [CONTACT NAME] Erro HTTP (tentativa {retry_count + 1}/{max_retries}): HTTP {e.response.status_code}")
                
                # Só retry para erros 5xx
                if e.response.status_code >= 500:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count
                        logger.info(f"⏳ [CONTACT NAME] Aguardando {wait_time}s antes de retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ [CONTACT NAME] Falhou após {max_retries} tentativas")
                        return
                else:
                    # Erros 4xx - não retry
                    logger.error(f"❌ [CONTACT NAME] Erro do cliente (não retry): HTTP {e.response.status_code}")
                    return
    
    except Exception as e:
        logger.error(f"❌ [CONTACT NAME] Erro inesperado ao buscar nome: {e}", exc_info=True)


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

