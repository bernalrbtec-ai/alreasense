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
import re
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import IntegrityError
from apps.chat.webhooks import send_read_receipt
from apps.notifications.whatsapp_providers import get_sender
from apps.chat.utils.instance_state import (
    should_defer_instance,
    InstanceTemporarilyUnavailable,
    compute_backoff,
)
from apps.chat.utils.metrics import record_latency, record_error

logger = logging.getLogger(__name__)
send_logger = logging.getLogger("flow.chat.send")
read_logger = logging.getLogger("flow.chat.read")
log = send_logger


def _broadcast_message_failed(message_id) -> None:
    """Notifica o frontend que a mensagem falhou (status=failed) para exibir ícone de falha / 'Falhou'."""
    try:
        from apps.chat.models import Message
        from apps.chat.utils.websocket import broadcast_message_status_update
        msg = Message.objects.select_related('conversation').filter(id=message_id).first()
        if msg and getattr(msg, 'conversation', None) is not None:
            broadcast_message_status_update(msg)
    except Exception as e:
        log.warning("⚠️ [CHAT ENVIO] Broadcast status failed: %s", e)


def _extract_provider_message_id(data: Optional[Dict[str, Any]], provider_kind: str = 'evolution') -> Optional[str]:
    """Extrai message_id da resposta do provider (Evolution ou Meta)."""
    if not data:
        return None
    if provider_kind == 'meta':
        messages = data.get('messages') or []
        if messages and isinstance(messages[0], dict):
            return messages[0].get('id')
        return None
    return extract_evolution_message_id(data)


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
        from apps.chat.models import Message
        
        # ✅ VALIDAÇÃO: Verificar se mensagem existe antes de enfileirar
        try:
            message = Message.objects.get(id=message_id)
            logger.debug(f"✅ [CHAT TASKS] Mensagem {message_id} existe no banco - enfileirando")
        except Message.DoesNotExist:
            logger.error(
                f"❌ [CHAT TASKS] Mensagem {message_id} não existe no banco - NÃO enfileirando. "
                f"Isso pode indicar que a mensagem foi deletada ou nunca foi criada."
            )
            return  # Não enfileirar mensagem que não existe
        
        # ✅ LOG CRÍTICO: Confirmar que send_message_to_evolution.delay foi chamado
        logger.critical(f"📤 [CHAT TASKS] send_message_to_evolution.delay chamado para: {message_id}")
        enqueue_send_stream_message(message_id)
        logger.critical(f"📤 [CHAT TASKS] Mensagem {message_id} enfileirada com sucesso")


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
              message_key: dict = None, mime_type: str = None, jpeg_thumbnail: dict = None,
              meta_media_id: str = None):
        """Enfileira processamento de mídia recebida (RabbitMQ). Meta: use meta_media_id; Evolution: use message_key/evolution_api_url."""
        payload = {
            'tenant_id': tenant_id,
            'message_id': message_id,
            'media_url': media_url,
            'media_type': media_type,
            'instance_name': instance_name,
            'api_key': api_key,
            'evolution_api_url': evolution_api_url,
            'message_key': message_key,
            'mime_type': mime_type,
            'jpeg_thumbnail': jpeg_thumbnail,
        }
        if meta_media_id:
            payload['meta_media_id'] = meta_media_id
        delay_rabbitmq(QUEUE_PROCESS_INCOMING_MEDIA, payload)


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


class edit_message:
    """Producer: Edita mensagem enviada via Evolution API (Redis - 10x mais rápido)."""
    
    @staticmethod
    def delay(message_id: str, new_content: str, edited_by_id: int = None):
        """Enfileira edição de mensagem (Redis)."""
        from apps.chat.redis_queue import REDIS_QUEUE_EDIT_MESSAGE, enqueue_message
        enqueue_message(REDIS_QUEUE_EDIT_MESSAGE, {
            'message_id': message_id,
            'new_content': new_content,
            'edited_by_id': edited_by_id
        })


def enqueue_mark_as_read(conversation_id: str, message_id: str):
    """Producer auxiliar: enfileira envio de read receipt."""
    enqueue_mark_stream_message(conversation_id, message_id)


# ========== FUNÇÕES AUXILIARES PARA REAÇÕES ==========

async def send_reaction_to_evolution(message, emoji: str):
    """
    Envia reação para Evolution API ou Meta Cloud API conforme integration_type da instância.
    
    Args:
        message: Instância do modelo Message (deve ter message_id preenchido)
        emoji: Emoji da reação (ex: "👍", "❤️")
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    from apps.chat.models import Message
    from apps.notifications.models import WhatsAppInstance
    from apps.notifications.whatsapp_providers import get_sender
    from apps.connections.models import EvolutionConnection
    from channels.db import database_sync_to_async
    from django.db import close_old_connections
    from django.db.models import Q
    import httpx
    
    logger.info(f"👍 [REACTION] Enviando reação...")
    logger.info(f"   Message ID interno: {message.id}")
    logger.info(f"   Message ID externo: {message.message_id}")
    logger.info(f"   Emoji: {emoji}")
    
    try:
        close_old_connections()
        
        if not message.message_id:
            logger.error(f"❌ [REACTION] Mensagem {message.id} não tem message_id (não foi enviada pelo sistema)")
            return False
        
        # Buscar instância: preferir a da conversa (instance_name = phone_number_id para Meta)
        inst_name = (message.conversation.instance_name or '').strip()
        instance = None
        if inst_name:
            instance = await database_sync_to_async(
                lambda: WhatsAppInstance.objects.filter(
                    Q(instance_name=inst_name)
                    | Q(evolution_instance_name=inst_name)
                    | Q(phone_number_id=inst_name),
                    tenant=message.conversation.tenant,
                    is_active=True,
                    status='active',
                ).first()
            )()
        if not instance:
            instance = await database_sync_to_async(
                WhatsAppInstance.objects.filter(
                    tenant=message.conversation.tenant,
                    is_active=True,
                    status='active',
                ).first
            )()
        
        if not instance:
            logger.warning(f"⚠️ [REACTION] Nenhuma instância WhatsApp ativa para tenant {message.conversation.tenant.name}")
            return False
        
        # Meta Cloud: usar provider (send_reaction via Graph API).
        # Nota: em conversas de grupo, a Meta usa "to" = wa_id do destinatário; contact_phone
        # pode ser JID do grupo (ex: 123456789-123@g.us). Se reações em grupos Meta falharem,
        # validar formato do "to" na documentação da Meta.
        if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            sender = await database_sync_to_async(get_sender)(instance)
            if not sender:
                logger.warning(f"⚠️ [REACTION] Meta: provider não disponível para instância {instance.id}")
                return False
            phone = message.conversation.contact_phone or ''
            if '@' in phone:
                phone = phone.split('@')[0]
            phone = phone.lstrip('+').strip()
            if not phone:
                logger.error(f"❌ [REACTION] Meta: contact_phone vazio")
                return False
            if message.conversation.conversation_type == 'group':
                logger.debug(
                    "👍 [REACTION] Meta: conversa é grupo; enviando reação com to=%s (validar se Meta aceita)",
                    _mask_digits(phone) if phone else "vazio",
                )
            try:
                ok, _ = await asyncio.to_thread(
                    sender.send_reaction,
                    phone,
                    message.message_id,
                    emoji or '',
                )
                if ok:
                    logger.info(f"✅ [REACTION] Reação enviada via Meta Cloud API")
                return bool(ok)
            except Exception as e:
                logger.exception("❌ [REACTION] Meta send_reaction error: %s", e)
                return False
        
        # Evolution: usar Evolution API
        close_old_connections()
        evolution_server = await database_sync_to_async(
            EvolutionConnection.objects.filter(is_active=True).first
        )()
        
        if not evolution_server and not instance.api_url:
            logger.error(f"❌ [REACTION] Configuração da Evolution API não encontrada")
            return False
        
        base_url = (instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = instance.api_key or evolution_server.api_key
        instance_name = instance.instance_name
        
        # ✅ CORREÇÃO CRÍTICA: Preparar remoteJid no formato correto para Evolution API
        # Evolution API requer formato completo: número@s.whatsapp.net (individual) ou ID@g.us (grupo)
        if message.conversation.conversation_type == 'group':
            # Grupos: garantir formato @g.us
            remote_jid = message.conversation.contact_phone
            if not remote_jid.endswith('@g.us'):
                if remote_jid.endswith('@s.whatsapp.net'):
                    remote_jid = remote_jid.replace('@s.whatsapp.net', '@g.us')
                else:
                    remote_jid = f"{remote_jid.rstrip('@')}@g.us"
        else:
            # ✅ CORREÇÃO: Individuais precisam do formato completo: número@s.whatsapp.net
            # Não remover @s.whatsapp.net, apenas garantir que está no formato correto
            phone = message.conversation.contact_phone
            
            # Se já tem @s.whatsapp.net, usar direto
            if phone.endswith('@s.whatsapp.net'):
                remote_jid = phone
            else:
                # Se não tem sufixo, adicionar @s.whatsapp.net
                # Remover + se existir (Evolution API não precisa)
                phone_clean = phone.lstrip('+')
                remote_jid = f"{phone_clean}@s.whatsapp.net"
        
        # ✅ CORREÇÃO CRÍTICA: Preparar payload para Evolution API conforme documentação
        # Documentação: https://www.postman.com/agenciadgcode/evolution-api/request/5su0wie/send-reaction
        # Payload deve ter: key.remoteJid (com @s.whatsapp.net ou @g.us), key.id (message_id), key.fromMe, reaction
        
        # ✅ VALIDAÇÃO: Garantir que message_id existe
        if not message.message_id:
            logger.error(f"❌ [REACTION] Mensagem {message.id} não tem message_id (não foi enviada pelo sistema)")
            return False
        
        # ✅ CORREÇÃO CRÍTICA: fromMe deve ser True se a mensagem foi ENVIADA por nós (outgoing)
        # Se a mensagem foi RECEBIDA (incoming), fromMe deve ser False
        # Isso é importante para a Evolution API encontrar a mensagem correta
        from_me = message.direction == 'outgoing'
        
        logger.info(f"📋 [REACTION] Preparando payload:")
        logger.info(f"   Message ID interno: {message.id}")
        logger.info(f"   Message ID externo: {message.message_id}")
        logger.info(f"   Direction: {message.direction}")
        logger.info(f"   fromMe: {from_me}")
        logger.info(f"   RemoteJID: {_mask_remote_jid(remote_jid)}")
        logger.info(f"   Emoji: {emoji}")
        
        payload = {
            'key': {
                'remoteJid': remote_jid,  # ✅ Formato completo: número@s.whatsapp.net ou ID@g.us
                'id': message.message_id,  # ✅ ID externo da mensagem no WhatsApp (key.id do webhook)
                'fromMe': from_me  # ✅ True se mensagem foi enviada por nós, False se foi recebida
            },
            'reaction': emoji if emoji else ''  # ✅ Emoji vazio remove reação no WhatsApp
        }
        
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        endpoint = f"{base_url}/message/sendReaction/{instance_name}"
        
        logger.critical(f"📡 [REACTION] ====== ENVIANDO PARA EVOLUTION API ======")
        logger.critical(f"   Endpoint: {endpoint}")
        logger.critical(f"   Base URL: {base_url}")
        logger.critical(f"   Instance Name: {instance_name}")
        logger.critical(f"   API Key presente: {bool(api_key)}")
        logger.critical(f"   RemoteJID (mascado): {_mask_remote_jid(remote_jid)}")
        logger.critical(f"   RemoteJID completo: {remote_jid}")
        logger.critical(f"   Message ID interno: {message.id}")
        logger.critical(f"   Message ID externo: {message.message_id}")
        logger.critical(f"   Emoji: {emoji}")
        logger.critical(f"   Direction: {message.direction}")
        logger.critical(f"   fromMe: {from_me}")
        logger.critical(f"   Payload (mascado): {mask_sensitive_data(payload)}")
        logger.info(f"📡 [REACTION] Enviando para Evolution API...")
        logger.info(f"   Endpoint: {endpoint}")
        logger.info(f"   RemoteJID (mascado): {_mask_remote_jid(remote_jid)}")
        logger.info(f"   Message ID externo: {message.message_id}")
        logger.info(f"   Emoji: {emoji}")
        logger.info(f"   Payload (mascado): {mask_sensitive_data(payload)}")
        
        # ✅ CORREÇÃO: Implementar retry com backoff exponencial para reações
        # Reações podem falhar por timeout ou problemas temporários de rede
        max_retries = 3
        retry_delays = [1.0, 2.0, 4.0]  # 1s, 2s, 4s
        
        for attempt in range(max_retries):
            try:
                logger.info(f"📡 [REACTION] Tentativa {attempt + 1}/{max_retries}...")
                
                # ✅ CORREÇÃO: Aumentar timeout para 30s (reação pode demorar mais)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers
                    )
                    
                    # ✅ CORREÇÃO: Evolution API retorna 201 Created para reações, não 200
                    logger.critical(f"📋 [REACTION] Resposta recebida: Status {response.status_code}")
                    logger.critical(f"   Response Headers: {dict(response.headers)}")
                    logger.critical(f"   Response Text (primeiros 500 chars): {response.text[:500]}")
                    
                    if response.status_code in (200, 201):
                        logger.critical(f"✅ [REACTION] ====== SUCESSO AO ENVIAR ======")
                        logger.info(f"✅ [REACTION] Reação enviada com sucesso para Evolution API (status: {response.status_code})")
                        try:
                            response_json = response.json()
                            logger.critical(f"   Response JSON: {response_json}")
                        except:
                            logger.critical(f"   Response não é JSON válido")
                        return True
                    else:
                        logger.critical(f"❌ [REACTION] ====== ERRO HTTP {response.status_code} ======")
                        logger.warning(f"⚠️ [REACTION] Erro {response.status_code} ao enviar reação (tentativa {attempt + 1}/{max_retries}):")
                        logger.warning(f"   Resposta: {response.text[:200]}")
                        
                        # Se não é erro temporário (5xx), não tentar novamente
                        if response.status_code < 500:
                            logger.error(f"❌ [REACTION] Erro permanente ({response.status_code}), não tentando novamente")
                            return False
                        
                        # Se é última tentativa, retornar False
                        if attempt == max_retries - 1:
                            logger.error(f"❌ [REACTION] Falha após {max_retries} tentativas")
                            return False
                        
                        # Aguardar antes de tentar novamente
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                        
            except httpx.TimeoutException as e:
                # ✅ httpx.ReadTimeout é subclasse de TimeoutException, então captura ambos
                logger.warning(f"⚠️ [REACTION] Timeout na tentativa {attempt + 1}/{max_retries}: {type(e).__name__}")
                
                # Se é última tentativa, retornar False
                if attempt == max_retries - 1:
                    logger.error(f"❌ [REACTION] Falha após {max_retries} tentativas devido a timeout")
                    return False
                
                # Aguardar antes de tentar novamente
                await asyncio.sleep(retry_delays[attempt])
                continue
                
            except (httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning(f"⚠️ [REACTION] Erro de conexão/rede na tentativa {attempt + 1}/{max_retries}: {type(e).__name__}")
                
                # Se é última tentativa, retornar False
                if attempt == max_retries - 1:
                    logger.error(f"❌ [REACTION] Falha após {max_retries} tentativas devido a erro de conexão/rede")
                    return False
                
                # Aguardar antes de tentar novamente
                await asyncio.sleep(retry_delays[attempt])
                continue
                
    except Exception as e:
        logger.error(f"❌ [REACTION] Erro inesperado ao enviar reação para Evolution API: {e}", exc_info=True)
        return False


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
    from django.db import close_old_connections
    import httpx
    
    send_logger.info("📤 [CHAT ENVIO] Iniciando envio | message_id=%s retry=%s", message_id, retry_count)

    log = send_logger

    overall_start = time.perf_counter()

    try:
        # ✅ CORREÇÃO CRÍTICA: Fechar conexões antigas antes de operações de banco
        close_old_connections()
        
        # Busca mensagem com todos os relacionamentos necessários para serialização
        try:
            message = await database_sync_to_async(
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
        except Message.DoesNotExist:
            # ✅ CORREÇÃO: Mensagem não existe - pode ter sido deletada ou nunca criada
            log.error(
                "❌ [CHAT ENVIO] Mensagem não encontrada no banco | message_id=%s retry=%s",
                message_id,
                retry_count
            )
            # Verificar se mensagem foi deletada recentemente (pode ser race condition)
            from django.utils import timezone
            from datetime import timedelta
            # Se for primeira tentativa, pode ser race condition - não fazer nada
            # Se for retry, mensagem realmente não existe
            if retry_count > 0:
                log.warning(
                    "⚠️ [CHAT ENVIO] Mensagem não encontrada após retry - abortando | message_id=%s",
                    message_id
                )
            else:
                log.warning(
                    "⚠️ [CHAT ENVIO] Mensagem não encontrada na primeira tentativa - pode ser race condition | message_id=%s",
                    message_id
                )
            return  # Abortar processamento
        
        log.debug(
            "✅ Mensagem carregada | conversation=%s tenant=%s content_preview=%s",
            message.conversation.contact_phone,
            message.conversation.tenant.name,
            (message.content or '')[:50],
        )
        
        # Se for nota interna, não envia
        if message.is_internal:
            message.status = 'sent'
            close_old_connections()
            await database_sync_to_async(message.save)(update_fields=['status'])
            log.info("📝 Nota interna criada (não enviada ao WhatsApp)")
            return
        
        # Busca instância WhatsApp ativa do tenant
        # ✅ CORREÇÃO MULTI-INSTÂNCIA: Priorizar instance_name da conversa (que recebeu a mensagem)
        log.debug("🔍 Buscando instância WhatsApp ativa...")
        
        # ✅ CORREÇÃO: Fechar conexões antigas antes de nova operação de banco
        close_old_connections()
        
        from django.db.models import Q
        instance = None
        inst_name = (message.conversation.instance_name or '').strip()
        if inst_name:
            # Lookup por instance_name / evolution_instance_name (Evolution)
            # Não exigir status='active' para não falhar em instâncias com status 'inactive' em produção
            instance = await database_sync_to_async(
                lambda: WhatsAppInstance.objects.filter(
                    Q(instance_name=inst_name) | Q(evolution_instance_name=inst_name),
                    tenant=message.conversation.tenant,
                    is_active=True,
                ).first()
            )()
            # Se instance_name é só dígitos (numérico), pode ser phone_number_id da Meta
            if not instance and inst_name.isdigit():
                instance = await database_sync_to_async(
                    lambda: WhatsAppInstance.objects.filter(
                        phone_number_id=inst_name,
                        integration_type=WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD,
                        tenant=message.conversation.tenant,
                        is_active=True,
                    ).first()
                )()
        if not instance:
            instance = await database_sync_to_async(
                WhatsAppInstance.objects.filter(
                    tenant=message.conversation.tenant,
                    is_active=True,
                ).first
            )()
        
        if not instance:
            message.status = 'failed'
            message.error_message = 'Nenhuma instância WhatsApp ativa encontrada'
            close_old_connections()
            await database_sync_to_async(message.save)(update_fields=['status', 'error_message'])
            await database_sync_to_async(_broadcast_message_failed)(message.id)
            log.error("❌ Nenhuma instância WhatsApp ativa | tenant=%s", message.conversation.tenant.name)
            return
        
        log.debug(
            "✅ Instância ativa | nome=%s uuid=%s api_url=%s",
            instance.friendly_name,
            instance.instance_name,
            instance.api_url,
        )

        # Meta Cloud: não usa EvolutionConnection/QR; não defer por estado
        if getattr(instance, 'integration_type', None) != WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            defer, state_info = should_defer_instance(instance.instance_name)
        else:
            defer, state_info = False, None
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

        # ✅ CORREÇÃO: Verificação mais tolerante de connection_state
        # Meta Cloud: não usa connection_state Evolution; aceitar sempre
        connection_state = None if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD else instance.connection_state
        if connection_state:
            # Estados aceitos imediatamente
            if connection_state in ('open', 'connected', 'active'):
                log.debug("✅ [CHAT ENVIO] connection_state=%s (aceito)", connection_state)
            # Estados transitórios: aceitar se recente ou se já tentamos várias vezes
            elif connection_state == 'connecting':
                # Se já tentamos 2+ vezes, tentar mesmo assim (pode ser instabilidade temporária)
                if retry_count >= 2:
                    log.warning(
                        "⚠️ [CHAT ENVIO] connection_state=connecting mas retry_count=%s. Tentando mesmo assim.",
                        retry_count
                    )
                # Se é primeira tentativa, verificar se estado foi atualizado recentemente
                elif state_info and state_info.age < 5.0:
                    log.warning(
                        "⚠️ [CHAT ENVIO] connection_state=connecting mas estado recente (age=%.2fs). Tentando mesmo assim.",
                        state_info.age
                    )
                else:
                    wait_seconds = compute_backoff(retry_count)
                    log.warning(
                        "⏳ [CHAT ENVIO] connection_state=connecting (age=%.2fs). Reagendando em %ss.",
                        (state_info.age if state_info else -1),
                        wait_seconds,
                    )
                    raise InstanceTemporarilyUnavailable(instance.instance_name, {'state': connection_state}, wait_seconds)
            # Outros estados (close, closeTimeout, etc): sempre reagendar
            else:
                wait_seconds = compute_backoff(retry_count)
                log.warning(
                    "⏳ [CHAT ENVIO] connection_state=%s. Reagendando em %ss.",
                    connection_state,
                    wait_seconds,
                )
                raise InstanceTemporarilyUnavailable(instance.instance_name, {'state': connection_state}, wait_seconds)
        
        # Helper para tratar message_id duplicado
        async def handle_duplicate_message_id(evolution_message_id: str):
            from django.db import close_old_connections
            metadata = message.metadata or {}
            metadata['duplicate_message_id'] = evolution_message_id
            close_old_connections()
            existing_message = await database_sync_to_async(
                Message.objects.filter(message_id=evolution_message_id).exclude(id=message.id).first
            )()
            if existing_message:
                metadata['duplicate_of'] = str(existing_message.id)
                new_status = existing_message.status
                new_evolution_status = existing_message.evolution_status
            else:
                new_status = 'sent'
                new_evolution_status = 'sent'
            close_old_connections()
            await database_sync_to_async(
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
        # ✅ CRÍTICO: Recarregar conversa do banco para garantir dados atualizados
        from apps.chat.models import Conversation
        
        # ✅ VALIDAÇÃO CRÍTICA: Garantir que message.conversation_id corresponde à conversa carregada
        original_conversation_id = message.conversation_id
        logger.critical(f"🔒 [SEGURANÇA] ====== VALIDAÇÃO DE CONVERSA ======")
        logger.critical(f"   Message ID: {message.id}")
        logger.critical(f"   Message Conversation ID (original): {original_conversation_id}")
        
        # ✅ CORREÇÃO: Fechar conexões antigas antes de operação de banco
        from django.db import close_old_connections
        close_old_connections()
        
        conversation = await database_sync_to_async(
            Conversation.objects.select_related('tenant').get
        )(id=original_conversation_id)
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se conversation_id da mensagem corresponde à conversa carregada
        if str(conversation.id) != str(original_conversation_id):
            logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation ID não corresponde!")
            logger.critical(f"   Message Conversation ID: {original_conversation_id}")
            logger.critical(f"   Conversation Carregada ID: {conversation.id}")
            raise ValueError(f"Conversa carregada não corresponde à conversa da mensagem: {original_conversation_id} != {conversation.id}")
        
        # ✅ LOG CRÍTICO DE SEGURANÇA: Validar destinatário antes de enviar
        logger.critical(f"🔒 [SEGURANÇA] ====== VALIDAÇÃO DE DESTINATÁRIO ======")
        logger.critical(f"   Message ID: {message.id}")
        logger.critical(f"   Conversation ID: {conversation.id}")
        logger.critical(f"   Conversation Type (DB): {conversation.conversation_type}")
        logger.critical(f"   Contact Phone: {_mask_remote_jid(conversation.contact_phone)}")
        logger.critical(f"   Message Conversation ID (validado): {message.conversation_id}")
        
        def get_recipient():
            """Retorna número formatado (E.164 ou group jid) e versão mascarada."""
            # ✅ CRÍTICO: Usar APENAS conversation_type do banco (não inferir pelo formato)
            # Isso garante que mensagens individuais não sejam enviadas para grupos
            if conversation.conversation_type == 'group':
                group_id = (conversation.group_metadata or {}).get('group_id') or conversation.contact_phone
                group_id = (group_id or '').strip()
                
                # ✅ VALIDAÇÃO CRÍTICA: Se group_id termina com @s.whatsapp.net, é individual, não grupo!
                if group_id.endswith('@s.whatsapp.net'):
                    logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: group_id termina com @s.whatsapp.net (individual), não @g.us!")
                    logger.critical(f"   group_id: {_mask_remote_jid(group_id)}")
                    logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                    logger.critical(f"   Isso causaria envio para destinatário ERRADO!")
                    raise ValueError(f"Conversa marcada como grupo mas contact_phone é individual: {_mask_remote_jid(group_id)}")
                
                if group_id.endswith('@s.whatsapp.net'):
                    group_id = group_id.replace('@s.whatsapp.net', '@g.us')
                if not group_id.endswith('@g.us'):
                    group_id = f"{group_id.rstrip('@')}@g.us"
                
                logger.critical(f"✅ [SEGURANÇA] Destinatário GRUPO: {_mask_remote_jid(group_id)}")
                return group_id, _mask_remote_jid(group_id)
            
            # individuais
            phone_number = (conversation.contact_phone or '').strip()
            
            # ✅ VALIDAÇÃO CRÍTICA: Se phone_number termina com @g.us, é grupo, não individual!
            if phone_number.endswith('@g.us'):
                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: phone_number termina com @g.us (grupo), não individual!")
                logger.critical(f"   phone_number: {_mask_remote_jid(phone_number)}")
                logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                logger.critical(f"   Isso causaria envio para destinatário ERRADO!")
                raise ValueError(f"Conversa marcada como individual mas contact_phone é grupo: {_mask_remote_jid(phone_number)}")
            
            phone_number = phone_number.replace('@s.whatsapp.net', '')
            if not phone_number.startswith('+'):
                phone_number = f'+{phone_number.lstrip("+")}'
            
            logger.critical(f"✅ [SEGURANÇA] Destinatário INDIVIDUAL: {_mask_remote_jid(phone_number)}")
            return phone_number, _mask_remote_jid(phone_number)

        recipient_value, masked_recipient = get_recipient()
        phone = recipient_value
        
        # ✅ LOG CRÍTICO FINAL: Confirmar destinatário antes de enviar
        logger.critical(f"🔒 [SEGURANÇA] Destinatário FINAL confirmado:")
        logger.critical(f"   Tipo: {conversation.conversation_type}")
        logger.critical(f"   Destinatário: {masked_recipient}")
        logger.critical(f"   Message ID: {message.id}")
        logger.critical(f"   Conversation ID: {conversation.id}")
        
        content = message.content
        attachment_urls = message.metadata.get('attachment_urls', []) if message.metadata else []
        include_signature = message.metadata.get('include_signature', True) if message.metadata else True  # ✅ Por padrão inclui assinatura
        reply_to_uuid = message.metadata.get('reply_to') if message.metadata else None  # ✅ UUID interno da mensagem sendo respondida
        
        # ✅ LOG CRÍTICO: Verificar se reply_to está no metadata
        log.info(f"🔍 [CHAT ENVIO] Verificando reply_to na mensagem:")
        log.info(f"   Message ID: {message.id}")
        log.info(f"   Metadata completo: {message.metadata}")
        log.info(f"   reply_to (UUID): {reply_to_uuid}")
        
        # ✅ NOVO: Buscar message_id da Evolution da mensagem original (se reply_to existe)
        quoted_message_id = None
        quoted_remote_jid = None
        quoted_participant = None  # participant da mensagem citada (grupos/Evolution); sempre definido para evitar UnboundLocalError
        original_message = None  # ✅ Definir no escopo externo para uso posterior
        if reply_to_uuid:
            logger.critical(f"🔍 [CHAT ENVIO] ====== BUSCANDO MENSAGEM ORIGINAL PARA REPLY ======")
            logger.critical(f"   reply_to_uuid: {reply_to_uuid}")
            logger.critical(f"   conversation_id: {conversation.id}")
            logger.critical(f"   conversation_phone: {conversation.contact_phone}")
            logger.critical(f"   conversation_type: {conversation.conversation_type}")
            
            try:
                logger.critical(f"🔍 [CHAT ENVIO] Executando query no banco...")
                # ✅ CORREÇÃO: Fechar conexões antigas antes de operação de banco
                from django.db import close_old_connections
                close_old_connections()
                
                original_message = await database_sync_to_async(
                    Message.objects.select_related('conversation').prefetch_related('attachments').filter(
                        id=reply_to_uuid, 
                        conversation=conversation
                    ).first
                )()
                logger.critical(f"✅ [CHAT ENVIO] Query executada! Resultado: {'Encontrada' if original_message else 'NÃO encontrada'}")
                
                if original_message:
                    logger.critical(f"✅ [CHAT ENVIO] Mensagem original encontrada!")
                    logger.critical(f"   ID interno: {original_message.id}")
                    logger.critical(f"   message_id (Evolution): {original_message.message_id}")
                    logger.critical(f"   direction: {original_message.direction}")
                    logger.critical(f"   content: {original_message.content[:50] if original_message.content else 'Sem conteúdo'}...")
                    
                    if original_message.message_id:
                        quoted_message_id = original_message.message_id
                        logger.critical(f"✅ [CHAT ENVIO] message_id da Evolution encontrado: {_mask_digits(quoted_message_id)}")
                    else:
                        logger.error(f"❌ [CHAT ENVIO] Mensagem original encontrada mas SEM message_id (Evolution)!")
                        logger.error(f"   Isso significa que a mensagem ainda não foi enviada ou não recebeu webhook de confirmação")
                        logger.error(f"   Status da mensagem original: {original_message.status}")
                        logger.error(f"   evolution_status: {original_message.evolution_status}")
                else:
                    logger.error(f"❌ [CHAT ENVIO] Mensagem original NÃO encontrada!")
                    logger.error(f"   UUID procurado: {reply_to_uuid}")
                    logger.error(f"   Conversation ID: {conversation.id}")
                    
                    # Tentar buscar em qualquer conversa do tenant (pode estar em outra conversa?)
                    close_old_connections()
                    all_messages = await database_sync_to_async(list)(
                        Message.objects.filter(
                            id=reply_to_uuid
                        ).select_related('conversation', 'conversation__tenant')
                    )
                    logger.error(f"   Total de mensagens com esse UUID em TODOS os tenants: {len(all_messages)}")
                    for msg in all_messages:
                        logger.error(f"   - Encontrada em tenant: {msg.conversation.tenant.name} (conversa: {msg.conversation.contact_phone})")
                
                if original_message and original_message.message_id:
                    quoted_message_id = original_message.message_id
                    logger.critical(f"✅ [CHAT ENVIO] Mensagem original tem message_id: {_mask_digits(quoted_message_id)}")
                    
                    # ✅ NOVO: Incluir remoteJid da mensagem original (necessário para Evolution API)
                    # O remoteJid é o contact_phone da conversa (formato: 5517999999999@s.whatsapp.net)
                    quoted_participant = None  # ✅ NOVO: participant (quem enviou a mensagem original)
                    if original_message.conversation:
                        contact_phone = original_message.conversation.contact_phone
                        logger.critical(f"🔍 [CHAT ENVIO] Definindo quoted_remote_jid:")
                        logger.critical(f"   contact_phone: {contact_phone}")
                        logger.critical(f"   conversation_type: {original_message.conversation.conversation_type}")
                        
                        # ✅ FIX CRÍTICO: Remover + do início do telefone antes de adicionar @s.whatsapp.net
                        # O remoteJid não deve ter + quando está no formato @s.whatsapp.net
                        clean_phone = contact_phone.lstrip('+')
                        
                        # Se já tem @, usar direto (mas remover + se tiver)
                        if '@' in clean_phone:
                            quoted_remote_jid = clean_phone
                            logger.critical(f"✅ [CHAT ENVIO] quoted_remote_jid definido (já tinha @): {_mask_remote_jid(quoted_remote_jid)}")
                        else:
                            # Adicionar @s.whatsapp.net se for contato individual
                            if original_message.conversation.conversation_type == 'individual':
                                quoted_remote_jid = f"{clean_phone}@s.whatsapp.net"
                                logger.critical(f"✅ [CHAT ENVIO] quoted_remote_jid definido (individual): {_mask_remote_jid(quoted_remote_jid)}")
                            else:
                                # Para grupos, usar o JID do grupo diretamente
                                quoted_remote_jid = clean_phone
                                logger.critical(f"✅ [CHAT ENVIO] quoted_remote_jid definido (grupo): {_mask_remote_jid(quoted_remote_jid)}")
                        
                        # ✅ CORREÇÃO CRÍTICA: Determinar participant baseado na direção da mensagem original
                        # Se a mensagem original foi recebida (incoming), o participant é o remetente
                        # Se foi enviada por nós (outgoing), o participant pode ser vazio ou nosso número
                        if original_message.direction == 'incoming':
                            # Mensagem recebida: participant é quem enviou
                            if original_message.conversation.conversation_type == 'group':
                                # Para grupos: usar sender_phone se disponível
                                if original_message.sender_phone:
                                    sender_phone = original_message.sender_phone
                                    # Remover + se tiver
                                    sender_phone_clean = sender_phone.lstrip('+')
                                    if '@' in sender_phone_clean:
                                        quoted_participant = sender_phone_clean
                                    else:
                                        quoted_participant = f"{sender_phone_clean}@s.whatsapp.net"
                                    logger.critical(f"✅ [CHAT ENVIO] quoted_participant definido (grupo, sender_phone): {_mask_remote_jid(quoted_participant)}")
                                else:
                                    # Fallback: usar contact_phone da conversa (grupo) - não ideal mas funciona
                                    quoted_participant = quoted_remote_jid
                                    logger.warning(f"⚠️ [CHAT ENVIO] sender_phone não disponível, usando quoted_remote_jid como fallback")
                            else:
                                # Para mensagens individuais recebidas: participant é o contato da conversa
                                # O contact_phone já está no formato correto (com @s.whatsapp.net)
                                quoted_participant = quoted_remote_jid
                                logger.critical(f"✅ [CHAT ENVIO] quoted_participant definido (individual): {_mask_remote_jid(quoted_participant)}")
                        else:
                            # Mensagem enviada por nós: participant pode ser vazio ou nosso número
                            # Para mensagens enviadas por nós, geralmente não precisa de participant
                            quoted_participant = None
                            logger.critical(f"✅ [CHAT ENVIO] Mensagem original foi enviada por nós, quoted_participant = None")
                        
                        logger.info(f"💬 [CHAT ENVIO] Mensagem é resposta de: {reply_to_uuid}")
                        logger.info(f"   Evolution ID: {quoted_message_id}")
                        logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid) if quoted_remote_jid else 'N/A'}")
                        logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A (mensagem enviada por nós)'}")
                        logger.info(f"   Direction original: {original_message.direction}")
                    else:
                        logger.error(f"❌ [CHAT ENVIO] original_message não tem conversation!")
                        quoted_remote_jid = None  # Limpar se não tem conversation
                else:
                    logger.warning(f"⚠️ [CHAT ENVIO] Mensagem original não encontrada ou sem message_id: {reply_to_uuid}")
                    original_message = None  # Limpar se não encontrada
            except Exception as e:
                logger.critical(f"❌ [CHAT ENVIO] ====== ERRO AO BUSCAR MENSAGEM ORIGINAL ======")
                logger.critical(f"   Erro: {e}")
                logger.critical(f"   Tipo: {type(e).__name__}")
                logger.critical(f"   Traceback completo:", exc_info=True)
                original_message = None  # Limpar em caso de erro
        
        # ✍️ ASSINATURA AUTOMÁTICA: Adicionar nome do usuário no início da mensagem
        # Formato: *Nome Sobrenome:*\n\n{mensagem}
        # ✅ Só adiciona se include_signature=True no metadata
        # ✅ IMPORTANTE: Assinatura deve ser adicionada APENAS para envio (Evolution API)
        # ✅ CRÍTICO: NÃO modificar message.content - manter conteúdo original sem assinatura no banco
        logger.critical(f"✍️ [CHAT ENVIO] ====== VERIFICANDO ASSINATURA ======")
        logger.critical(f"   include_signature: {include_signature}")
        logger.critical(f"   content original (primeiros 50 chars): {content[:50] if content else 'VAZIO'}...")
        logger.critical(f"   É reply? {bool(reply_to_uuid)}")
        
        # ✅ CORREÇÃO: Criar variável separada para conteúdo com assinatura (apenas para envio)
        content_for_send = content  # Conteúdo que será enviado (pode ter assinatura)
        
        if include_signature and content:
            sender = message.sender  # ✅ Já carregado via select_related
            sender_name = (getattr(message, 'sender_name', None) or '').strip()
            full_name = None
            if sender:
                first_name = sender.first_name or ''
                last_name = sender.last_name or ''
                if first_name or last_name:
                    full_name = f"{first_name} {last_name}".strip()
            elif sender_name:
                # Mensagem da secretária (sender=None, sender_name=ex: "Bia")
                full_name = sender_name

            if full_name:
                # Evitar duplicar assinatura se o modelo (ex: secretária) já colocou na resposta
                content_stripped = content.strip()
                prefix_disse = f"{full_name} disse:"
                already_has_disse = content_stripped.lower().startswith(prefix_disse.lower())
                already_has_asterisk = content_stripped.startswith(f"*{full_name}:*")
                if already_has_disse:
                    # Conteúdo já tem "Bia disse:" (formato do chat). Para WhatsApp enviar só *Bia:* + corpo
                    body = content_stripped[len(prefix_disse):].lstrip("\n\t ")
                    content_for_send = f"*{full_name}:*\n\n" + (body or content_stripped)
                    # message.content manter como está (já tem "Bia disse:" para o chat)
                    logger.critical(f"✍️ [CHAT ENVIO] Assinatura já no conteúdo; envio para Evolution só *Nome:* + corpo")
                elif already_has_asterisk:
                    content_for_send = content  # Já no formato WhatsApp
                    logger.critical(f"✍️ [CHAT ENVIO] Conteúdo já com *Nome:*")
                else:
                    signature_for_send = f"*{full_name}:*\n\n"
                    content_for_send = signature_for_send + content
                    signature_for_db = f"{full_name} disse:\n\n"
                    message.content = signature_for_db + content
                    from channels.db import database_sync_to_async
                    from django.db import close_old_connections
                    close_old_connections()
                    await database_sync_to_async(message.save)(update_fields=['content'])
                    logger.critical(f"✍️ [CHAT ENVIO] ✅ Assinatura adicionada: {full_name}")
            elif sender and not (getattr(sender, 'first_name', '') or getattr(sender, 'last_name', '')):
                logger.warning(f"⚠️ [CHAT ENVIO] Sender sem nome")
            elif not sender and not sender_name:
                logger.warning(f"⚠️ [CHAT ENVIO] Sender ou content ausente (sender={bool(sender)}, content={bool(content)})")
        else:
            logger.info(f"✍️ [CHAT ENVIO] Assinatura desabilitada pelo usuário")
        
        # ✅ CORREÇÃO: Usar content_for_send daqui em diante para envio (Evolution API)
        
        logger.info("📱 [CHAT ENVIO] Destino=%s | tipo=%s", phone, conversation.conversation_type)
        
        # Buscar attachments para obter mime_type
        attachments_list = []
        if attachment_urls:
            from apps.chat.models import MessageAttachment
            from django.db import close_old_connections
            close_old_connections()
            attachments_list = await database_sync_to_async(list)(
                MessageAttachment.objects.filter(message=message).order_by('created_at')
            )
        
        # Envio via provider (Evolution ou Meta Cloud) quando disponível
        sender = await database_sync_to_async(get_sender)(instance)
        provider_kind = 'meta' if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD else 'evolution'
        if sender:
            from django.db import close_old_connections
            location_data = (message.metadata or {}).get('location_message', {})
            loc_lat, loc_lng = location_data.get('latitude'), location_data.get('longitude')
            quoted_content = None
            if original_message:
                quoted_content = (original_message.content or '').strip() or None
                if not quoted_content and getattr(original_message, 'attachments', None):
                    atts = list(original_message.attachments.all()) if hasattr(original_message.attachments, 'all') else []
                    if atts:
                        quoted_content = '📎 Anexo'
            try:
                last_ok = False
                last_data = {}
                if loc_lat is not None and loc_lng is not None and not attachment_urls:
                    last_ok, last_data = await asyncio.to_thread(
                        sender.send_location,
                        recipient_value,
                        float(loc_lat),
                        float(loc_lng),
                        location_data.get('name') or 'Localização',
                        location_data.get('address') or '',
                        quoted_message_id,
                        quoted_remote_jid=quoted_remote_jid,
                        quoted_message_content=quoted_content,
                        quoted_from_me=bool(original_message and original_message.direction == 'outgoing'),
                        quoted_participant=quoted_participant,
                    )
                elif attachment_urls and attachments_list:
                    for idx, url in enumerate(attachment_urls):
                        att = attachments_list[idx] if idx < len(attachments_list) else None
                        mime = att.mime_type if att else 'application/octet-stream'
                        fname = att.original_filename if att else 'file'
                        final_url = (att.short_url or url) if att else url
                        if mime.startswith('audio/'):
                            last_ok, last_data = await asyncio.to_thread(
                                sender.send_audio_ptt,
                                recipient_value,
                                final_url,
                                quoted_message_id,
                                quoted_remote_jid=quoted_remote_jid,
                                quoted_message_content=quoted_content,
                                quoted_from_me=bool(original_message and original_message.direction == 'outgoing'),
                                quoted_participant=quoted_participant,
                            )
                        else:
                            last_ok, last_data = await asyncio.to_thread(
                                sender.send_media,
                                recipient_value,
                                final_url,
                                mime,
                                content_for_send if not idx else None,
                                fname,
                                quoted_message_id,
                                quoted_remote_jid=quoted_remote_jid,
                                quoted_message_content=quoted_content,
                                quoted_from_me=bool(original_message and original_message.direction == 'outgoing'),
                                quoted_participant=quoted_participant,
                            )
                        if not last_ok:
                            break
                else:
                    # Texto puro (sem anexo nem localização)
                    # Meta: fora da janela 24h só pode enviar por template
                    if provider_kind == 'meta':
                        from apps.chat.whatsapp_24h import is_within_24h_window
                        within_24h = await database_sync_to_async(is_within_24h_window)(conversation)
                        if not within_24h:
                            meta = message.metadata or {}
                            wa_template_id = meta.get('wa_template_id')
                            if not wa_template_id:
                                close_old_connections()
                                await database_sync_to_async(
                                    Message.objects.filter(id=message.id).update
                                )(status='failed', error_message='Fora da janela 24h. Selecione um template aprovado para enviar.')
                                await database_sync_to_async(_broadcast_message_failed)(message.id)
                                log.warning(
                                    "❌ [CHAT ENVIO] Meta: fora da janela 24h sem template | conversation_id=%s",
                                    str(conversation.id),
                                )
                                return
                            try:
                                import uuid
                                uuid.UUID(str(wa_template_id))
                            except (ValueError, TypeError):
                                close_old_connections()
                                await database_sync_to_async(
                                    Message.objects.filter(id=message.id).update
                                )(status='failed', error_message='Template inválido (ID inválido).')
                                await database_sync_to_async(_broadcast_message_failed)(message.id)
                                return
                            from apps.notifications.models import WhatsAppTemplate
                            wa_template = await database_sync_to_async(
                                WhatsAppTemplate.objects.filter(
                                    id=wa_template_id,
                                    tenant_id=conversation.tenant_id,
                                    is_active=True,
                                ).first
                            )()
                            if not wa_template:
                                close_old_connections()
                                await database_sync_to_async(
                                    Message.objects.filter(id=message.id).update
                                )(status='failed', error_message='Template não encontrado ou inativo.')
                                await database_sync_to_async(_broadcast_message_failed)(message.id)
                                return
                            body_params = meta.get('body_parameters')
                            if not isinstance(body_params, (list, tuple)):
                                body_params = wa_template.body_parameters_default or []
                            body_params = list(body_params)
                            # Se o template espera pelo menos 1 parâmetro (ex.: {{1}} = nome) e não foi enviado nenhum, usa o nome do contato
                            if not body_params and (conversation.contact_name or conversation.contact_phone):
                                body_params = [str(conversation.contact_name or conversation.contact_phone or 'Cliente').strip() or 'Cliente']
                            last_ok, last_data = await asyncio.to_thread(
                                sender.send_template,
                                recipient_value,
                                wa_template.template_id,
                                wa_template.language_code or 'pt_BR',
                                body_params,
                            )
                        else:
                            last_ok, last_data = await asyncio.to_thread(
                                sender.send_text,
                                recipient_value,
                                content_for_send or '',
                                quoted_message_id,
                            )
                    else:
                        last_ok, last_data = await asyncio.to_thread(
                            sender.send_text,
                            recipient_value,
                            content_for_send or '',
                            quoted_message_id,
                        )
                if last_ok:
                    evo_id = _extract_provider_message_id(last_data, provider_kind)
                    if evo_id:
                        close_old_connections()
                        await database_sync_to_async(
                            Message.objects.filter(id=message.id).update
                        )(message_id=evo_id)
                    close_old_connections()
                    await database_sync_to_async(
                        Message.objects.filter(id=message.id).update
                    )(status='sent', evolution_status='sent')
                    from apps.chat.utils.websocket import broadcast_conversation_updated, broadcast_message_received
                    msg_obj = await database_sync_to_async(
                        Message.objects.select_related('conversation', 'sender').prefetch_related('attachments').get
                    )(id=message.id)
                    await database_sync_to_async(broadcast_message_received)(msg_obj)
                    await database_sync_to_async(broadcast_conversation_updated)(message.conversation, message_id=str(message.id))
                    log.info("✅ [CHAT ENVIO] Mensagem enviada via provider (provider=%s)", provider_kind)
                    return
                err = last_data.get('error', '') or str(last_data)
                close_old_connections()
                await database_sync_to_async(
                    Message.objects.filter(id=message.id).update
                )(status='failed', error_message=err[:500])
                log.warning("❌ [CHAT ENVIO] Provider retornou falha (provider=%s): %s", provider_kind, err[:200])
                await database_sync_to_async(_broadcast_message_failed)(message.id)
                # Meta: marcar instância em alerta se erro for de token/sessão (usuário vê em Configurações)
                if provider_kind == 'meta' and instance:
                    try:
                        updated = await database_sync_to_async(instance.set_meta_token_error_if_applicable)(err)
                        if updated:
                            log.warning("⚠️ [CHAT ENVIO] Instância Meta marcada em alerta (token/sessão). Contate o administrador.")
                    except Exception as e2:
                        log.warning("⚠️ [CHAT ENVIO] Não foi possível marcar instância em alerta: %s", e2)
                return
            except Exception as e:
                log.exception("❌ [CHAT ENVIO] Erro ao enviar via provider: %s", e)
                close_old_connections()
                err_msg = str(e)[:500]
                await database_sync_to_async(
                    Message.objects.filter(id=message.id).update
                )(status='failed', error_message=err_msg)
                await database_sync_to_async(_broadcast_message_failed)(message.id)
                if provider_kind == 'meta' and instance:
                    try:
                        await database_sync_to_async(instance.set_meta_token_error_if_applicable)(err_msg)
                    except Exception as e2:
                        log.warning("⚠️ [CHAT ENVIO] Não foi possível marcar instância em alerta: %s", e2)
                return
        
        # Meta sem provider válido: não usar Evolution
        if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            close_old_connections()
            await database_sync_to_async(
                Message.objects.filter(id=message.id).update
            )(status='failed', error_message='Instância Meta sem phone_number_id/access_token válidos')
            await database_sync_to_async(_broadcast_message_failed)(message.id)
            return
        
        # Envia via Evolution API (path legado quando get_sender não usado)
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
            
            # 📍 LOCALIZAÇÃO: Enviar via sendLocation (Evolution API)
            location_data = (message.metadata or {}).get('location_message', {})
            loc_lat = location_data.get('latitude')
            loc_lng = location_data.get('longitude')
            if loc_lat is not None and loc_lng is not None and not attachment_urls:
                loc_name = location_data.get('name', 'Localização')
                loc_address = location_data.get('address', '')
                payload = {
                    'number': recipient_value,
                    'latitude': float(loc_lat),
                    'longitude': float(loc_lng),
                    'name': str(loc_name)[:255] if loc_name else 'Localização',
                    'address': str(loc_address)[:500] if loc_address else str(loc_name)[:500] or 'Localização',
                }
                # Adicionar quoted se for resposta
                if quoted_message_id and quoted_remote_jid:
                    payload['quoted'] = {
                        'key': {'id': quoted_message_id},
                        'message': {'conversation': (content or '')[:100] or '.'}
                    }
                endpoint = f"{base_url}/message/sendLocation/{instance.instance_name}"
                log.info(f"📍 [CHAT] Enviando localização via sendLocation | lat={loc_lat} lng={loc_lng}")
                try:
                    resp = await client.post(endpoint, headers=headers, json=payload)
                    if resp.status_code in (200, 201):
                        data = resp.json() if resp.text else {}
                        evo_id = (data.get('key') or {}).get('id')
                        if evo_id:
                            close_old_connections()
                            await database_sync_to_async(
                                Message.objects.filter(id=message.id).update
                            )(message_id=evo_id, status='sent', evolution_status='sent')
                        log.info(f"✅ [CHAT] Localização enviada com sucesso")
                        # Broadcast via utilitário padrão (mesmo grupo chat_tenant_xxx que consumer usa)
                        from apps.chat.utils.websocket import broadcast_message_received
                        close_old_connections()
                        msg_obj = await database_sync_to_async(
                            Message.objects.select_related('conversation', 'sender').prefetch_related('attachments').get
                        )(id=message.id)
                        await database_sync_to_async(broadcast_message_received)(msg_obj)
                        return
                    else:
                        err_text = resp.text[:500] if resp.text else ''
                        log.error(f"❌ [CHAT] sendLocation falhou: {resp.status_code} - {err_text}")
                        close_old_connections()
                        await database_sync_to_async(
                            Message.objects.filter(id=message.id).update
                        )(status='failed', error_message=err_text[:500])
                        await database_sync_to_async(_broadcast_message_failed)(message.id)
                except Exception as e:
                    log.error(f"❌ [CHAT] Erro ao enviar localização: {e}", exc_info=True)
                    close_old_connections()
                    await database_sync_to_async(
                        Message.objects.filter(id=message.id).update
                    )(status='failed', error_message=str(e)[:500])
                    await database_sync_to_async(_broadcast_message_failed)(message.id)
                # ✅ CRÍTICO: Retornar após tentar localização (sucesso ou falha) para não cair no envio de texto
                return
            
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
                        # ✅ VALIDAÇÃO CRÍTICA: Verificar se recipient_value corresponde ao conversation_type
                        logger.critical(f"🔒 [SEGURANÇA] ====== VALIDAÇÃO DE DESTINATÁRIO (ÁUDIO) ======")
                        logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                        logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                        logger.critical(f"   Message ID: {message.id}")
                        logger.critical(f"   Conversation ID: {conversation.id}")
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é grupo, recipient_value DEVE terminar com @g.us
                        if conversation.conversation_type == 'group':
                            if not recipient_value.endswith('@g.us'):
                                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é grupo mas recipient_value não termina com @g.us!")
                                logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                                logger.critical(f"   Isso causaria envio para destinatário ERRADO!")
                                raise ValueError(f"Conversa é grupo mas destinatário não é grupo: {_mask_remote_jid(recipient_value)}")
                            logger.critical(f"✅ [SEGURANÇA] Destinatário GRUPO validado (áudio): {_mask_remote_jid(recipient_value)}")
                        else:
                            # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é individual, recipient_value NÃO deve terminar com @g.us
                            if recipient_value.endswith('@g.us'):
                                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é individual mas recipient_value termina com @g.us!")
                                logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                                logger.critical(f"   Isso causaria envio para grupo ao invés de individual!")
                                raise ValueError(f"Conversa é individual mas destinatário é grupo: {_mask_remote_jid(recipient_value)}")
                            logger.critical(f"✅ [SEGURANÇA] Destinatário INDIVIDUAL validado (áudio): {_mask_remote_jid(recipient_value)}")
                        
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
                        
                        logger.critical(f"✅ [SEGURANÇA] Payload de áudio criado com destinatário validado:")
                        logger.critical(f"   number: {_mask_remote_jid(payload['number'])}")
                        logger.critical(f"   conversation_type: {conversation.conversation_type}")
                        logger.critical(f"   message_id: {message.id}")
                        logger.critical(f"   conversation_id: {conversation.id}")
                        
                        # ✅ NOVO: Adicionar options.quoted se for resposta (formato Evolution API)
                        if quoted_message_id and quoted_remote_jid and original_message:
                            original_content = original_message.content or ''
                            if not original_content:
                                attachments_list = list(original_message.attachments.all())
                                if attachments_list:
                                    original_content = '📎 Áudio'
                            
                            # ✅ CORREÇÃO CRÍTICA: Montar quoted.key com participant quando necessário
                            quoted_key = {
                                        'remoteJid': quoted_remote_jid,
                                        'fromMe': original_message.direction == 'outgoing',
                                        'id': quoted_message_id
                            }
                            
                            # ✅ CORREÇÃO: Adicionar participant se for grupo e mensagem foi recebida (incoming)
                            # O participant é obrigatório para grupos quando a mensagem original foi enviada por outro participante
                            if quoted_participant and original_message.conversation.conversation_type == 'group':
                                quoted_key['participant'] = quoted_participant
                                logger.info(f"💬 [CHAT ENVIO] Adicionando participant ao quoted.key (grupo, áudio): {_mask_remote_jid(quoted_participant)}")
                            
                            payload['options'] = {
                                'quoted': {
                                    'key': quoted_key,
                                    'message': {
                                        'conversation': original_content[:100] if original_content else 'Áudio'
                                    }
                                }
                            }
                            logger.info(f"💬 [CHAT ENVIO] Adicionando options.quoted ao áudio")
                            logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid)}")
                            logger.info(f"   Message ID: {quoted_message_id}")
                            logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A'}")
                            logger.info(f"   FromMe: {original_message.direction == 'outgoing'}")
                        
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
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Verificar se recipient_value corresponde ao conversation_type
                        logger.critical(f"🔒 [SEGURANÇA] ====== VALIDAÇÃO DE DESTINATÁRIO (MÍDIA) ======")
                        logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                        logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                        logger.critical(f"   Message ID: {message.id}")
                        logger.critical(f"   Conversation ID: {conversation.id}")
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é grupo, recipient_value DEVE terminar com @g.us
                        if conversation.conversation_type == 'group':
                            if not recipient_value.endswith('@g.us'):
                                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é grupo mas recipient_value não termina com @g.us!")
                                logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                                logger.critical(f"   Isso causaria envio para destinatário ERRADO!")
                                raise ValueError(f"Conversa é grupo mas destinatário não é grupo: {_mask_remote_jid(recipient_value)}")
                            logger.critical(f"✅ [SEGURANÇA] Destinatário GRUPO validado (mídia): {_mask_remote_jid(recipient_value)}")
                        else:
                            # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é individual, recipient_value NÃO deve terminar com @g.us
                            if recipient_value.endswith('@g.us'):
                                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é individual mas recipient_value termina com @g.us!")
                                logger.critical(f"   Recipient Value: {_mask_remote_jid(recipient_value)}")
                                logger.critical(f"   Isso causaria envio para grupo ao invés de individual!")
                                raise ValueError(f"Conversa é individual mas destinatário é grupo: {_mask_remote_jid(recipient_value)}")
                            logger.critical(f"✅ [SEGURANÇA] Destinatário INDIVIDUAL validado (mídia): {_mask_remote_jid(recipient_value)}")
                        
                        # ✅ Evolution API NÃO usa mediaMessage wrapper!
                        # Estrutura correta: direto no root
                        # ✅ USAR SHORT_URL (já configurado acima)
                        payload = {
                            'number': recipient_value,
                            'media': final_url,      # URL CURTA! (/media/{hash})
                            'mediatype': mediatype,  # lowercase!
                            'fileName': filename     # Nome do arquivo
                        }
                        
                        logger.critical(f"✅ [SEGURANÇA] Payload de mídia criado com destinatário validado:")
                        logger.critical(f"   number: {_mask_remote_jid(payload['number'])}")
                        logger.critical(f"   conversation_type: {conversation.conversation_type}")
                        logger.critical(f"   message_id: {message.id}")
                        logger.critical(f"   conversation_id: {conversation.id}")
                        if content:
                            payload['caption'] = content  # Caption direto no root também
                        
                        # ✅ NOVO: Adicionar options.quoted se for resposta (formato Evolution API)
                        if quoted_message_id and quoted_remote_jid and original_message:
                            original_content = original_message.content or ''
                            if not original_content:
                                # Detectar tipo de anexo (já carregado via prefetch_related)
                                attachments_list = list(original_message.attachments.all())
                                if attachments_list:
                                    attachment = attachments_list[0]
                                    if attachment.is_image:
                                        original_content = '📷 Imagem'
                                    elif attachment.is_video:
                                        original_content = '🎥 Vídeo'
                                    elif attachment.is_audio:
                                        original_content = '🎵 Áudio'
                                    else:
                                        original_content = '📎 Documento'
                                else:
                                    original_content = '📎 Anexo'
                            
                            # ✅ CORREÇÃO CRÍTICA: Montar quoted.key com participant quando necessário
                            quoted_key = {
                                        'remoteJid': quoted_remote_jid,
                                        'fromMe': original_message.direction == 'outgoing',
                                        'id': quoted_message_id
                            }
                            
                            # ✅ CORREÇÃO: Adicionar participant se for grupo e mensagem foi recebida (incoming)
                            # O participant é obrigatório para grupos quando a mensagem original foi enviada por outro participante
                            if quoted_participant and original_message.conversation.conversation_type == 'group':
                                quoted_key['participant'] = quoted_participant
                                logger.info(f"💬 [CHAT ENVIO] Adicionando participant ao quoted.key (grupo): {_mask_remote_jid(quoted_participant)}")
                            
                            payload['options'] = {
                                'quoted': {
                                    'key': quoted_key,
                                    'message': {
                                        'conversation': original_content[:100] if original_content else 'Mensagem'
                                    }
                                }
                            }
                            logger.info(f"💬 [CHAT ENVIO] Adicionando options.quoted à mídia")
                            logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid)}")
                            logger.info(f"   Message ID: {quoted_message_id}")
                            logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A'}")
                            logger.info(f"   FromMe: {original_message.direction == 'outgoing'}")
                    
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
                        
                        # ✅ CORREÇÃO CRÍTICA: Erros 500/503 são temporários - fazer retry
                        if response.status_code >= 500:
                            error_msg = f'Erro temporário do servidor ao enviar mídia (HTTP {response.status_code}): {response.text[:200]}'
                            log.warning(
                                "⏳ [CHAT ENVIO] Erro temporário do servidor ao enviar mídia (HTTP %s). Reagendando para retry.",
                                response.status_code
                            )
                            raise InstanceTemporarilyUnavailable(
                                instance.instance_name,
                                {'http_status': response.status_code, 'error': error_msg, 'media_type': mediatype},
                                compute_backoff(retry_count)
                            )
                        
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
                            
                            # ✅ CORREÇÃO: Adicionar options.quoted no fallback também se for reply
                            if quoted_message_id and quoted_remote_jid and original_message:
                                original_content = original_message.content or ''
                                if not original_content:
                                    attachments_list = list(original_message.attachments.all())
                                    if attachments_list:
                                        original_content = '📎 Áudio'
                                
                                # ✅ CORREÇÃO CRÍTICA: Montar quoted.key com participant quando necessário
                                quoted_key = {
                                    'remoteJid': quoted_remote_jid,
                                    'fromMe': original_message.direction == 'outgoing',
                                    'id': quoted_message_id
                                }
                                
                                # ✅ CORREÇÃO: Adicionar participant se for grupo e mensagem foi recebida (incoming)
                                if quoted_participant and original_message.conversation.conversation_type == 'group':
                                    quoted_key['participant'] = quoted_participant
                                    logger.info(f"💬 [CHAT ENVIO FALLBACK] Adicionando participant ao quoted.key (grupo, áudio): {_mask_remote_jid(quoted_participant)}")
                                
                                fb_payload['options'] = {
                                    'quoted': {
                                        'key': quoted_key,
                                        'message': {
                                            'conversation': original_content[:100] if original_content else 'Áudio'
                                        }
                                    }
                                }
                                logger.info(f"💬 [CHAT ENVIO FALLBACK] Adicionando options.quoted ao áudio (fallback)")
                                logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid)}")
                                logger.info(f"   Message ID: {quoted_message_id}")
                                logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A'}")
                            
                            logger.warning("⚠️ [CHAT] sendWhatsAppAudio retornou 404. Tentando fallback sendMedia (audio)...")
                            logger.info(f"   FB Endpoint: {fb_endpoint}")
                            logger.info(f"   FB Payload (mascado): {mask_sensitive_data(fb_payload)}")
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
                            
                            # ✅ CORREÇÃO CRÍTICA: Erros 500/503 são temporários - fazer retry
                            if fb_resp.status_code >= 500:
                                error_msg = f'Erro temporário do servidor ao enviar mídia (fallback, HTTP {fb_resp.status_code}): {fb_resp.text[:200]}'
                                log.warning(
                                    "⏳ [CHAT ENVIO] Erro temporário do servidor ao enviar mídia (fallback, HTTP %s). Reagendando para retry.",
                                    fb_resp.status_code
                                )
                                raise InstanceTemporarilyUnavailable(
                                    instance.instance_name,
                                    {'http_status': fb_resp.status_code, 'error': error_msg, 'media_type': 'audio', 'fallback': True},
                                    compute_backoff(retry_count)
                                )
                            
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
                            from django.db import close_old_connections
                            close_old_connections()
                            await database_sync_to_async(message.save)(update_fields=['message_id'])
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
                # ✅ CORREÇÃO: Garantir que número não tenha @s.whatsapp.net para individuais
                final_number = recipient_value
                if conversation.conversation_type == 'individual':
                    # Remover @s.whatsapp.net se ainda estiver presente
                    final_number = final_number.replace('@s.whatsapp.net', '').strip()
                    # Garantir que começa com +
                    if not final_number.startswith('+'):
                        final_number = f'+{final_number.lstrip("+")}'
                
                # ✅ CORREÇÃO: Validar que conteúdo não está vazio após processamento
                if not content or not content.strip():
                    logger.error(f"❌ [CHAT ENVIO] Conteúdo vazio após processamento! message_id={message_id}")
                    message.status = 'failed'
                    message.error_message = 'Conteúdo da mensagem está vazio'
                    from django.db import close_old_connections
                    close_old_connections()
                    await database_sync_to_async(message.save)(update_fields=['status', 'error_message'])
                    await database_sync_to_async(_broadcast_message_failed)(message.id)
                    return
                
                # ✅ FORMATO CORRETO: Evolution API usa 'text' no root e 'quoted' no root
                # Documentação: https://www.postman.com/agenciadgcode/evolution-api/request/0nthjkr/send-text
                # ✅ LOG CRÍTICO: Verificar conteúdo original vs conteúdo para envio
                logger.critical(f"✍️ [CHAT ENVIO] ====== CRIANDO PAYLOAD DE TEXTO ======")
                logger.critical(f"   content original (sem assinatura, primeiros 150 chars): {content[:150] if content else 'VAZIO'}...")
                logger.critical(f"   content_for_send (com assinatura, primeiros 150 chars): {content_for_send[:150] if content_for_send else 'VAZIO'}...")
                logger.critical(f"   content tem assinatura? {'*' in content[:50] if content else False}")
                logger.critical(f"   content_for_send tem assinatura? {'*' in content_for_send[:50] if content_for_send else False}")
                logger.critical(f"   content length: {len(content) if content else 0}")
                logger.critical(f"   content_for_send length: {len(content_for_send) if content_for_send else 0}")
                
                # ✅ VALIDAÇÃO CRÍTICA FINAL: Verificar se final_number corresponde ao conversation_type
                logger.critical(f"🔒 [SEGURANÇA] ====== VALIDAÇÃO FINAL DO DESTINATÁRIO ======")
                logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                logger.critical(f"   Final Number: {_mask_remote_jid(final_number)}")
                logger.critical(f"   Message ID: {message.id}")
                logger.critical(f"   Conversation ID: {conversation.id}")
                
                # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é grupo, final_number DEVE terminar com @g.us
                if conversation.conversation_type == 'group':
                    if not final_number.endswith('@g.us'):
                        logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é grupo mas final_number não termina com @g.us!")
                        logger.critical(f"   Final Number: {_mask_remote_jid(final_number)}")
                        logger.critical(f"   Isso causaria envio para destinatário ERRADO!")
                        raise ValueError(f"Conversa é grupo mas destinatário não é grupo: {_mask_remote_jid(final_number)}")
                    logger.critical(f"✅ [SEGURANÇA] Destinatário GRUPO validado: {_mask_remote_jid(final_number)}")
                else:
                    # ✅ VALIDAÇÃO CRÍTICA: Se conversation_type é individual, final_number NÃO deve terminar com @g.us
                    if final_number.endswith('@g.us'):
                        logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation é individual mas final_number termina com @g.us!")
                        logger.critical(f"   Final Number: {_mask_remote_jid(final_number)}")
                        logger.critical(f"   Isso causaria envio para grupo ao invés de individual!")
                        raise ValueError(f"Conversa é individual mas destinatário é grupo: {_mask_remote_jid(final_number)}")
                    logger.critical(f"✅ [SEGURANÇA] Destinatário INDIVIDUAL validado: {_mask_remote_jid(final_number)}")
                
                # ✅ CORREÇÃO: Usar content_for_send (com assinatura) para envio, mas manter content original no banco
                payload = {
                    'number': final_number,
                    'text': content_for_send.strip()  # ✅ Usar content_for_send (pode ter assinatura)
                }
                
                logger.critical(f"✅ [SEGURANÇA] Payload criado com destinatário validado:")
                logger.critical(f"   number: {_mask_remote_jid(payload['number'])}")
                logger.critical(f"   conversation_type: {conversation.conversation_type}")
                logger.critical(f"   message_id: {message.id}")
                logger.critical(f"   conversation_id: {conversation.id}")
                
                logger.critical(f"   payload['text'] (primeiros 150 chars): {payload['text'][:150] if payload.get('text') else 'VAZIO'}...")
                
                # ✅ LOG CRÍTICO: Verificar se reply foi detectado antes de adicionar quoted
                logger.critical(f"🔍 [CHAT ENVIO] ====== VERIFICANDO SE DEVE ADICIONAR 'quoted' ======")
                logger.critical(f"   quoted_message_id: {quoted_message_id}")
                logger.critical(f"   quoted_message_id existe? {bool(quoted_message_id)}")
                logger.critical(f"   quoted_remote_jid: {quoted_remote_jid}")
                logger.critical(f"   quoted_remote_jid existe? {bool(quoted_remote_jid)}")
                logger.critical(f"   original_message: {original_message is not None}")
                logger.critical(f"   original_message existe? {bool(original_message)}")
                logger.critical(f"   Condição completa (todos True?): {bool(quoted_message_id and quoted_remote_jid and original_message)}")
                
                # ✅ CORREÇÃO: Adicionar 'quoted' no root (não dentro de 'options') se for resposta
                if quoted_message_id and quoted_remote_jid and original_message:
                    logger.critical(f"✅ [CHAT ENVIO] TODAS AS CONDIÇÕES ATENDIDAS! Adicionando 'quoted' ao payload...")
                    # Buscar conteúdo original da mensagem para incluir no quoted
                    original_content = original_message.content or ''
                    if not original_content:
                        # Verificar se tem anexos (já carregado via prefetch_related)
                        attachments_list = list(original_message.attachments.all())
                        if attachments_list:
                            attachment = attachments_list[0]
                            if attachment.is_image:
                                original_content = '📷 Imagem'
                            elif attachment.is_video:
                                original_content = '🎥 Vídeo'
                            elif attachment.is_audio:
                                original_content = '🎵 Áudio'
                            else:
                                original_content = '📎 Documento'
                        else:
                            original_content = 'Mensagem'
                    
                    # ✅ FIX: Limitar e limpar conteúdo para evitar caracteres especiais problemáticos
                    # Remover quebras de linha e caracteres de controle
                    clean_content = original_content.replace('\n', ' ').replace('\r', ' ').strip()
                    # Limitar a 100 caracteres
                    clean_content = clean_content[:100] if clean_content else 'Mensagem'
                    
                    # ✅ FORMATO CORRETO: quoted.key precisa de id, remoteJid e fromMe
                    # Documentação Evolution API: https://www.postman.com/agenciadgcode/evolution-api/request/0nthjkr/send-text
                    # O formato completo ajuda a Evolution API a encontrar a mensagem original corretamente
                    quoted_key = {
                        'id': quoted_message_id,  # ID da mensagem original
                        'remoteJid': quoted_remote_jid,  # JID do destinatário (necessário para Evolution encontrar a mensagem)
                        'fromMe': original_message.direction == 'outgoing'  # Se mensagem original foi enviada por nós
                    }
                    
                    # ✅ Adicionar participant apenas se necessário (para grupos ou mensagens recebidas)
                    if quoted_participant:
                        quoted_key['participant'] = quoted_participant
                    
                    # ✅ FORMATO CORRETO: 'quoted' no root (não dentro de 'options')
                    payload['quoted'] = {
                        'key': quoted_key,
                        'message': {
                            'conversation': clean_content
                        }
                    }
                    
                    logger.critical(f"💬 [CHAT ENVIO] Payload quoted.key completo:")
                    logger.critical(f"   id: {_mask_digits(quoted_key.get('id'))}")
                    logger.critical(f"   remoteJid: {_mask_remote_jid(quoted_key.get('remoteJid'))}")
                    logger.critical(f"   fromMe: {quoted_key.get('fromMe')}")
                    logger.critical(f"   participant: {_mask_remote_jid(quoted_key.get('participant')) if quoted_key.get('participant') else 'N/A'}")
                    logger.info(f"💬 [CHAT ENVIO] Adicionando 'quoted' no root (formato correto Evolution API)")
                    logger.info(f"   Message ID: {_mask_digits(quoted_message_id)}")
                    logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid)}")
                    logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A'}")
                    logger.info(f"   Original content (limpo): {clean_content[:50]}...")
                    logger.info(f"   📋 Payload com quoted (mascado): %s", mask_sensitive_data(payload))
                    logger.info(f"   📋 Payload com quoted (JSON formatado): %s", json.dumps(mask_sensitive_data(payload), indent=2, ensure_ascii=False))
                    
                    # ✅ LOG CRÍTICO: Verificar estrutura do quoted antes de enviar
                    if 'quoted' in payload:
                        logger.info(f"✅ [CHAT ENVIO] 'quoted' confirmado no payload!")
                        logger.info(f"   quoted.key.id: {_mask_digits(payload['quoted']['key'].get('id', 'N/A'))}")
                        logger.info(f"   quoted.key.remoteJid: {_mask_remote_jid(payload['quoted']['key'].get('remoteJid', 'N/A'))}")
                        logger.info(f"   quoted.key.participant: {_mask_remote_jid(payload['quoted']['key'].get('participant', 'N/A'))}")
                    else:
                        logger.error(f"❌ [CHAT ENVIO] 'quoted' NÃO está no payload! Isso é um erro!")
                
                # ✅ NOVO: Adicionar menções se for grupo e tiver mentions no metadata
                if conversation.conversation_type == 'group':
                    metadata = message.metadata or {}
                    mentions = metadata.get('mentions', [])
                    mention_everyone = metadata.get('mention_everyone', False)  # ✅ NOVO: Flag para @everyone
                    
                    # ✅ LOG CRÍTICO: Verificar se há menções para processar
                    logger.critical(f"🔍 [CHAT ENVIO] ====== VERIFICANDO MENÇÕES ======")
                    logger.critical(f"   conversation_type: {conversation.conversation_type}")
                    logger.critical(f"   mentions no metadata: {mentions}")
                    logger.critical(f"   mentions é lista? {isinstance(mentions, list)}")
                    logger.critical(f"   mentions length: {len(mentions) if isinstance(mentions, list) else 'N/A'}")
                    logger.critical(f"   mention_everyone: {mention_everyone}")
                    
                    # ✅ NOVO: Suporte a @everyone (mencionar todos)
                    if mention_everyone:
                        logger.info(f"🔔 [CHAT ENVIO] Mencionando TODOS os participantes do grupo (@everyone)")
                        payload['mentions'] = {
                            'everyOne': True,
                            'mentioned': []  # Array vazio quando everyOne é True
                        }
                        logger.info(f"✅ [CHAT ENVIO] Payload mentions configurado para mencionar todos")
                    elif mentions and isinstance(mentions, list) and len(mentions) > 0:
                        # ✅ CORREÇÃO CRÍTICA: Usar informações do grupo para fazer match correto
                        # Buscar participantes do grupo em group_metadata
                        # ✅ CORREÇÃO: Usar database_sync_to_async para refresh_from_db em contexto assíncrono
                        from channels.db import database_sync_to_async
                        from django.db import close_old_connections
                        close_old_connections()
                        await database_sync_to_async(conversation.refresh_from_db)()  # Garantir dados atualizados
                        group_metadata = conversation.group_metadata or {}
                        group_participants = group_metadata.get('participants', [])
                        
                        logger.info(f"🔍 [CHAT ENVIO] Processando {len(mentions)} menção(ões) usando {len(group_participants)} participantes do grupo")
                        
                        # ✅ MELHORIA: Buscar contatos cadastrados primeiro (mesma lógica do recebimento)
                        from apps.contacts.models import Contact
                        from apps.notifications.services import normalize_phone
                        from apps.contacts.signals import normalize_phone_for_search
                        
                        # Buscar TODOS os contatos do tenant e criar mapa telefone normalizado -> nome
                        phone_to_contact = {}
                        # ✅ FIX: Usar tenant_id ao invés de conversation.tenant para evitar erro de contexto assíncrono
                        tenant_id = conversation.tenant_id
                        from django.db import close_old_connections
                        close_old_connections()
                        all_contacts = await database_sync_to_async(list)(
                            Contact.objects.filter(
                                tenant_id=tenant_id
                            ).exclude(phone__isnull=True).exclude(phone='').values('phone', 'name')
                        )
                        
                        logger.info(f"🔍 [CHAT ENVIO] Buscando contatos cadastrados: {len(all_contacts)} contatos no tenant")
                        
                        for contact in all_contacts:
                            contact_phone_raw = contact.get('phone', '').strip()
                            if not contact_phone_raw:
                                continue
                            normalized_contact_phone = normalize_phone(contact_phone_raw)
                            if normalized_contact_phone:
                                contact_name = contact.get('name', '').strip()
                                if contact_name:
                                    phone_to_contact[normalized_contact_phone] = contact_name
                                    logger.debug(f"   ✅ [CHAT ENVIO] Contato cadastrado mapeado: {normalized_contact_phone} -> {contact_name}")
                        
                        logger.info(f"✅ [CHAT ENVIO] {len(phone_to_contact)} contatos cadastrados mapeados")
                        
                        # Criar mapas para busca rápida: nome -> participante, phone -> participante, jid -> participante
                        participants_by_name = {}  # nome normalizado -> participante
                        participants_by_phone = {}  # phone normalizado -> participante
                        participants_by_jid = {}  # jid -> participante
                        
                        for p in group_participants:
                            participant_name = (p.get('name') or '').strip().lower()
                            participant_phone = p.get('phone', '')
                            participant_jid = p.get('jid', '')
                            participant_phone_number = p.get('phoneNumber', '') or p.get('phone_number', '')
                            
                            # Mapear por nome
                            if participant_name:
                                participants_by_name[participant_name] = p
                            
                            # Mapear por telefone (normalizado)
                            if participant_phone:
                                normalized = normalize_phone(participant_phone)
                                if normalized:
                                    participants_by_phone[normalized] = p
                                    participants_by_phone[normalize_phone_for_search(normalized)] = p
                                # Também mapear sem normalização
                                phone_clean = participant_phone.replace('+', '').replace(' ', '').replace('-', '').strip()
                                if phone_clean:
                                    participants_by_phone[phone_clean] = p
                            
                            # Mapear por phoneNumber (JID real do telefone)
                            if participant_phone_number:
                                phone_raw = participant_phone_number.split('@')[0]
                                if phone_raw:
                                    normalized = normalize_phone(phone_raw)
                                    if normalized:
                                        participants_by_phone[normalized] = p
                                        participants_by_phone[normalize_phone_for_search(normalized)] = p
                                    phone_clean = phone_raw.replace('+', '').replace(' ', '').replace('-', '').strip()
                                    if phone_clean:
                                        participants_by_phone[phone_clean] = p
                            
                            # Mapear por JID
                            if participant_jid:
                                participants_by_jid[participant_jid] = p
                        
                        # Processar cada menção e fazer match com participantes do grupo
                        mention_phones = []
                        mention_jids_map = {}  # ✅ TESTE: Mapear telefone -> JID completo para usar no array mentioned
                        for m in mentions:
                            mention_name = (m.get('name') or '').strip().lower()
                            mention_phone = m.get('phone', '')
                            mention_jid = m.get('jid', '')
                            
                            matched_participant = None
                            matched_contact_phone = None  # ✅ NOVO: Telefone do contato cadastrado encontrado
                            
                            # ✅ PRIORIDADE 1: Buscar em CONTATOS CADASTRADOS primeiro (mesma lógica do recebimento)
                            # ✅ FIX: Verificar se mention_phone não é LID antes de normalizar
                            if mention_phone and not mention_phone.endswith('@lid'):
                                try:
                                    normalized_mention_phone = normalize_phone(mention_phone)
                                    if normalized_mention_phone and normalized_mention_phone in phone_to_contact:
                                        # Contato cadastrado encontrado! Usar telefone dele
                                        matched_contact_phone = normalized_mention_phone
                                        contact_name = phone_to_contact[normalized_mention_phone]
                                        logger.info(f"   ✅ [CHAT ENVIO] Contato cadastrado encontrado: {contact_name} ({_mask_digits(normalized_mention_phone)})")
                                    else:
                                        logger.debug(f"   ⚠️ [CHAT ENVIO] mention_phone não encontrado em contatos cadastrados: {_mask_digits(mention_phone)}")
                                except Exception as e:
                                    logger.debug(f"   ⚠️ [CHAT ENVIO] Erro ao normalizar mention_phone: {e}")
                            elif mention_phone and mention_phone.endswith('@lid'):
                                logger.debug(f"   ⚠️ [CHAT ENVIO] mention_phone é LID, não pode buscar em contatos cadastrados: {mention_phone}")
                            
                            # ✅ PRIORIDADE 2: Buscar por JID nos participantes do grupo (incluindo LIDs)
                            if not matched_contact_phone and mention_jid and mention_jid in participants_by_jid:
                                matched_participant = participants_by_jid[mention_jid]
                                logger.debug(f"   📌 Menção encontrada por JID: {mention_jid}")
                            
                            # ✅ PRIORIDADE 3: Buscar por nome nos participantes do grupo (quando usuário digita @contato)
                            elif not matched_contact_phone and mention_name and mention_name in participants_by_name:
                                matched_participant = participants_by_name[mention_name]
                                logger.debug(f"   📌 Menção encontrada por nome: {mention_name}")
                            
                            # ✅ PRIORIDADE 4: Buscar por telefone nos participantes do grupo
                            # ✅ FIX: Não tentar normalizar se mention_phone é LID
                            elif not matched_contact_phone and mention_phone and not mention_phone.endswith('@lid'):
                                phone_clean = mention_phone.replace('+', '').replace(' ', '').replace('-', '').strip()
                                try:
                                    normalized = normalize_phone(mention_phone)
                                    if normalized and normalized in participants_by_phone:
                                        matched_participant = participants_by_phone[normalized]
                                        logger.debug(f"   📌 Menção encontrada por telefone normalizado: {normalized}")
                                    elif phone_clean and phone_clean in participants_by_phone:
                                        matched_participant = participants_by_phone[phone_clean]
                                        logger.debug(f"   📌 Menção encontrada por telefone limpo: {phone_clean}")
                                except Exception as e:
                                    logger.debug(f"   ⚠️ [CHAT ENVIO] Erro ao normalizar mention_phone para busca: {e}")
                            
                            # ✅ PRIORIDADE MÁXIMA: Se encontrou contato cadastrado, usar telefone dele
                            if matched_contact_phone:
                                # Extrair apenas dígitos (remover +)
                                phone_digits = matched_contact_phone.lstrip('+')
                                if phone_digits:
                                    mention_phones.append(phone_digits)
                                    # ✅ TESTE: Tentar encontrar JID correspondente para este telefone
                                    # Buscar nos participantes do grupo por phoneNumber
                                    found_jid = None
                                    for p in group_participants:
                                        p_phone_number = p.get('phoneNumber') or p.get('phone_number', '')
                                        if p_phone_number:
                                            p_phone_raw = p_phone_number.split('@')[0]
                                            if p_phone_raw == phone_digits:
                                                found_jid = p_phone_number  # Usar phoneNumber completo (JID)
                                                break
                                    if found_jid:
                                        mention_jids_map[phone_digits] = found_jid
                                        logger.info(f"   ✅ [CHAT ENVIO] Menção adicionada via contato cadastrado: {_mask_digits(phone_digits)} (JID: {_mask_remote_jid(found_jid)})")
                                    else:
                                        logger.info(f"   ✅ [CHAT ENVIO] Menção adicionada via contato cadastrado: {_mask_digits(phone_digits)} (sem JID correspondente)")
                            
                            # Se encontrou participante do grupo, usar phoneNumber (telefone real) para menção
                            elif matched_participant:
                                participant_phone_number = matched_participant.get('phoneNumber') or matched_participant.get('phone_number', '')
                                participant_jid = matched_participant.get('jid', '')
                                
                                # ✅ CRÍTICO: Evolution API requer telefone real, NÃO LID
                                # Sempre usar phoneNumber (telefone real) se disponível
                                if participant_phone_number:
                                    # Extrair apenas os dígitos do phoneNumber (formato: 5517996196795@s.whatsapp.net)
                                    phone_raw = participant_phone_number.split('@')[0]
                                    if phone_raw and len(phone_raw) >= 10:  # Validar que tem pelo menos 10 dígitos
                                        mention_phones.append(phone_raw)
                                        # ✅ TESTE: Armazenar JID completo (phoneNumber) para usar no array mentioned
                                        mention_jids_map[phone_raw] = participant_phone_number
                                        logger.info(f"   ✅ Menção adicionada via phoneNumber: {_mask_digits(phone_raw)} (JID: {_mask_remote_jid(participant_phone_number)}, nome: {matched_participant.get('name', 'N/A')})")
                                    else:
                                        logger.warning(f"   ⚠️ phoneNumber inválido ou muito curto: {phone_raw}")
                                else:
                                    # ✅ CRÍTICO: Se não tem phoneNumber, não podemos enviar menção válida
                                    # Evolution API não aceita LIDs no array mentioned
                                    logger.error(f"   ❌ [CHAT ENVIO] Participante encontrado mas SEM phoneNumber válido!")
                                    logger.error(f"   ❌ [CHAT ENVIO] JID: {matched_participant.get('jid', 'N/A')}")
                                    logger.error(f"   ❌ [CHAT ENVIO] Phone: {matched_participant.get('phone', 'N/A')}")
                                    logger.error(f"   ❌ [CHAT ENVIO] Não é possível enviar menção sem telefone real (Evolution API requer número, não LID)")
                            else:
                                # Se não encontrou participante nem contato, tentar buscar phoneNumber real usando JID/LID
                                # ✅ CRÍTICO: Evolution API requer telefone real, NÃO LID
                                if mention_jid:
                                    logger.debug(f"   🔍 [CHAT ENVIO] Tentando encontrar phoneNumber real para JID/LID: {mention_jid}")
                                    # Buscar em todos os participantes por JID (pode ser LID)
                                    found_phone = False
                                    for p in group_participants:
                                        if p.get('jid') == mention_jid:
                                            participant_phone_number = p.get('phoneNumber') or p.get('phone_number', '')
                                            if participant_phone_number:
                                                phone_raw = participant_phone_number.split('@')[0]
                                                if phone_raw and len(phone_raw) >= 10:  # Validar que tem pelo menos 10 dígitos
                                                    mention_phones.append(phone_raw)
                                                    # ✅ TESTE: Armazenar JID completo (phoneNumber) para usar no array mentioned
                                                    mention_jids_map[phone_raw] = participant_phone_number
                                                    logger.info(f"   ✅ [CHAT ENVIO] Menção adicionada via phoneNumber do JID/LID: {_mask_digits(phone_raw)} (JID: {_mask_remote_jid(participant_phone_number)})")
                                                    found_phone = True
                                                    break
                                    
                                    if not found_phone:
                                        logger.error(f"   ❌ [CHAT ENVIO] Não foi possível encontrar phoneNumber real para JID/LID: {mention_jid}")
                                        logger.error(f"   ❌ [CHAT ENVIO] Evolution API requer telefone real, não LID. Menção será ignorada.")
                                elif mention_phone and not mention_phone.endswith('@lid'):
                                    # ✅ VALIDAÇÃO: Verificar se phone não é o número do grupo
                                    group_phone = conversation.contact_phone.replace('+', '').replace(' ', '').strip()
                                    if '@' in group_phone:
                                        group_phone = group_phone.split('@')[0]
                                    
                                    phone_clean = mention_phone.replace('+', '').replace(' ', '').replace('-', '').strip()
                                    # Validar que é telefone válido (pelo menos 10 dígitos)
                                    if phone_clean and len(phone_clean) >= 10 and phone_clean != group_phone:
                                        mention_phones.append(phone_clean)
                                        logger.debug(f"   📌 Menção adicionada via phone direto (fallback): {phone_clean}")
                                    else:
                                        logger.warning(f"   ⚠️ Phone {phone_clean} é inválido ou é o número do grupo! Pulando menção...")
                                elif mention_phone and mention_phone.endswith('@lid'):
                                    logger.error(f"   ❌ [CHAT ENVIO] mention_phone é LID mas não encontrou participante: {mention_phone}")
                                    logger.error(f"   ❌ [CHAT ENVIO] Evolution API requer telefone real, não LID. Menção será ignorada.")
                        
                        if mention_phones:
                            # ✅ CORREÇÃO CRÍTICA: Formato correto da Evolution API para menções
                            # Formato: objeto com "everyOne" (boolean) e "mentioned" (array de números)
                            # Números devem estar no formato internacional SEM + e SEM @
                            # IMPORTANTE: O número no texto DEVE SER EXATAMENTE IGUAL ao número no array mentioned
                            # Exemplo: {"everyOne": false, "mentioned": ["5517996196795"]}
                            
                            # Normalizar números: remover + e garantir formato internacional
                            mentioned_numbers = []
                            for phone in mention_phones:
                                # Remover @ se tiver (caso venha como JID)
                                phone_clean = phone.split('@')[0] if '@' in phone else phone
                                # Remover + se tiver
                                phone_clean = phone_clean.lstrip('+')
                                # Garantir que é apenas números
                                phone_clean = ''.join(filter(str.isdigit, phone_clean))
                                if phone_clean and len(phone_clean) >= 10:  # Validar que tem pelo menos 10 dígitos
                                    mentioned_numbers.append(phone_clean)
                                    logger.debug(f"   ✅ [CHAT ENVIO] Número normalizado para menção: {_mask_digits(phone_clean)}")
                            
                            if mentioned_numbers:
                                # ✅ FORMATO CORRETO: objeto com everyOne e mentioned (apenas números)
                                payload['mentions'] = {
                                    'everyOne': False,  # Para mencionar todos, usar True e mentioned vazio
                                    'mentioned': mentioned_numbers  # Array de números sem + e sem @
                                }
                                logger.info(f"✅ [CHAT ENVIO] Adicionando {len(mentioned_numbers)} menção(ões) à mensagem")
                                logger.info(f"   Formato: objeto com 'everyOne' e 'mentioned'")
                                logger.info(f"   Menções (mascaradas): {', '.join([_mask_digits(num) for num in mentioned_numbers])}")
                                logger.info(f"   Menções (formato completo): {json.dumps(payload['mentions'], ensure_ascii=False)}")
                                
                                # ✅ CRÍTICO: Substituir nomes por telefones no texto
                                # Evolution API requer que o texto tenha @telefone, não @nome
                                # ✅ CORREÇÃO: Usar content_for_send (pode ter assinatura) para substituição
                                if mentions and isinstance(mentions, list):
                                    # Criar mapeamento nome -> telefone
                                    name_to_phone_map = {}
                                    logger.info(f"🔍 [CHAT ENVIO] Processando {len(mentions)} menção(ões) para substituição de nomes")
                                    
                                    for mention_meta in mentions:
                                        mention_name = mention_meta.get('name', '').strip()
                                        mention_phone = mention_meta.get('phone', '')
                                        logger.debug(f"   📋 [CHAT ENVIO] Menção: name='{mention_name}', phone='{_mask_digits(mention_phone) if mention_phone else 'N/A'}'")
                                        
                                        # Buscar telefone correspondente no array mentioned_numbers
                                        if mention_name and mention_phone:
                                            # Normalizar telefone para comparar
                                            phone_normalized = mention_phone.replace('+', '').replace(' ', '').replace('-', '').strip()
                                            phone_normalized = ''.join(filter(str.isdigit, phone_normalized))
                                            # Verificar se este telefone está no array mentioned_numbers
                                            # ✅ CRÍTICO: O número no texto DEVE SER EXATAMENTE IGUAL ao do array mentioned
                                            for mentioned_num in mentioned_numbers:
                                                if phone_normalized == mentioned_num:
                                                    # ✅ CRÍTICO: Usar o número EXATO do array mentioned para substituição no texto
                                                    name_to_phone_map[mention_name] = mentioned_num
                                                    logger.info(f"   ✅ [CHAT ENVIO] Mapeamento criado: '{mention_name}' -> {_mask_digits(mentioned_num)}")
                                                    break
                                    
                                    # Substituir @Nome por @Telefone no texto (usar content_for_send)
                                    if name_to_phone_map:
                                        text_before = payload['text']
                                        logger.info(f"🔍 [CHAT ENVIO] Texto ANTES da substituição: {text_before[:200]}")
                                        logger.info(f"🔍 [CHAT ENVIO] Mapeamentos disponíveis: {list(name_to_phone_map.keys())}")
                                        
                                        # ✅ FIX: Ordenar nomes por tamanho (mais longos primeiro) para evitar substituições parciais
                                        # Exemplo: "Paulo J. M. Bernal" deve ser substituído antes de "Paulo"
                                        sorted_names = sorted(name_to_phone_map.items(), key=lambda x: len(x[0]), reverse=True)
                                        logger.info(f"🔍 [CHAT ENVIO] Nomes ordenados por tamanho (mais longos primeiro): {[name for name, _ in sorted_names]}")
                                        
                                        for name, phone in sorted_names:
                                            # ✅ CRÍTICO: Substituir nome completo no texto
                                            # O nome pode ter espaços, pontos, etc. Precisamos capturar tudo
                                            logger.info(f"   🔍 [CHAT ENVIO] Tentando substituir: '@{name}' -> '@{_mask_digits(phone)}'")
                                            logger.info(f"   📝 [CHAT ENVIO] Texto atual (primeiros 200 chars): {payload['text'][:200]}")
                                            
                                            # ✅ ESTRATÉGIA 1: Tentar substituição exata (case-insensitive)
                                            escaped_name = re.escape(name)
                                            pattern_exact = rf'@{escaped_name}(?=\s|$|,|\.|!|\?|:)'
                                            replacement = f'@{phone}'
                                            
                                            new_text = re.sub(pattern_exact, replacement, payload['text'], flags=re.IGNORECASE, count=0)
                                            
                                            if new_text != payload['text']:
                                                logger.info(f"   ✅ [CHAT ENVIO] Substituição EXATA realizada: '@{name}' -> '@{_mask_digits(phone)}'")
                                                payload['text'] = new_text
                                                continue
                                            
                                            # ✅ ESTRATÉGIA 2: Se não encontrou, tentar busca flexível para nomes compostos
                                            name_parts = name.split()
                                            if len(name_parts) > 1:
                                                logger.warning(f"   ⚠️ [CHAT ENVIO] Padrão exato não encontrado, tentando busca flexível para nome composto...")
                                                
                                                # Tentar diferentes variações de espaços
                                                # Exemplo: "Paulo J. M. Bernal" pode estar como "Paulo  J. M. Bernal" (espaços extras)
                                                first_part = name_parts[0]
                                                remaining_parts = ' '.join(name_parts[1:])
                                                
                                                # Pattern flexível: aceita 1 ou mais espaços entre as partes
                                                flexible_pattern = rf'@{re.escape(first_part)}\s+{re.escape(remaining_parts)}(?=\s|$|,|\.|!|\?|:)'
                                                new_text_flexible = re.sub(flexible_pattern, replacement, payload['text'], flags=re.IGNORECASE, count=0)
                                                
                                                if new_text_flexible != payload['text']:
                                                    logger.info(f"   ✅ [CHAT ENVIO] Substituição FLEXÍVEL realizada: '@{name}' -> '@{_mask_digits(phone)}'")
                                                    payload['text'] = new_text_flexible
                                                    continue
                                                
                                                # ✅ ESTRATÉGIA 3: Buscar manualmente no texto (último recurso)
                                                logger.warning(f"   ⚠️ [CHAT ENVIO] Busca flexível também falhou, tentando busca manual...")
                                                
                                                # Buscar todas as ocorrências de @ seguido de texto no texto atual
                                                text_lower = payload['text'].lower()
                                                name_lower = name.lower()
                                                
                                                # Procurar por @nome no texto (case-insensitive)
                                                at_index = text_lower.find(f'@{name_lower}')
                                                if at_index != -1:
                                                    # Verificar se há espaço ou fim após o nome
                                                    after_name_index = at_index + len(f'@{name_lower}')
                                                    if after_name_index >= len(payload['text']) or payload['text'][after_name_index] in [' ', '\n', ',', '.', '!', '?', ':']:
                                                        # Substituir manualmente
                                                        text_before_mention = payload['text'][:at_index]
                                                        text_after_mention = payload['text'][after_name_index:]
                                                        payload['text'] = text_before_mention + replacement + text_after_mention
                                                        logger.info(f"   ✅ [CHAT ENVIO] Substituição MANUAL realizada: '@{name}' -> '@{_mask_digits(phone)}'")
                                                        continue
                                            
                                            logger.error(f"   ❌ [CHAT ENVIO] NÃO FOI POSSÍVEL substituir '@{name}' no texto!")
                                            logger.error(f"   📝 [CHAT ENVIO] Texto completo: {payload['text']}")
                                            logger.error(f"   📝 [CHAT ENVIO] Nome procurado: '{name}'")
                                        
                                        if text_before != payload['text']:
                                            logger.info(f"✅ [CHAT ENVIO] Texto atualizado com telefones reais:")
                                            logger.info(f"   Antes: {text_before[:200]}")
                                            logger.info(f"   Depois: {payload['text'][:200]}")
                                            
                                            # ✅ VALIDAÇÃO CRÍTICA: Verificar se todos os números no texto estão no array mentioned
                                            # Extrair todos os números mencionados no texto (formato @número)
                                            mentioned_in_text = re.findall(r'@(\d+)', payload['text'])
                                            logger.info(f"🔍 [CHAT ENVIO] Números mencionados no texto: {[f'@{num}' for num in mentioned_in_text]}")
                                            logger.info(f"🔍 [CHAT ENVIO] Números no array mentioned: {mentioned_numbers}")
                                            
                                            # Verificar se todos os números do texto estão no array mentioned
                                            all_match = True
                                            for num_in_text in mentioned_in_text:
                                                if num_in_text not in mentioned_numbers:
                                                    logger.error(f"❌ [CHAT ENVIO] Número no texto '{num_in_text}' NÃO está no array mentioned!")
                                                    all_match = False
                                            
                                            if all_match:
                                                logger.info(f"✅ [CHAT ENVIO] Validação OK: Todos os números no texto estão no array mentioned")
                                            else:
                                                logger.error(f"❌ [CHAT ENVIO] Validação FALHOU: Números no texto não correspondem ao array mentioned!")
                                            
                                            # ✅ CORREÇÃO CRÍTICA: Atualizar message.content após substituição de menções
                                            # O payload['text'] tem assinatura com asteriscos (*Nome:*), mas no banco deve ter formato "Nome disse:"
                                            # Extrair apenas o conteúdo da mensagem (sem assinatura) do payload
                                            content_from_payload = payload['text']
                                            
                                            # Remover assinatura com asteriscos do payload (formato: *Nome:*\n\n)
                                            if sender and (sender.first_name or sender.last_name):
                                                full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                                                if full_name:
                                                    # Remover assinatura com asteriscos
                                                    signature_pattern_asterisk = rf'\*{re.escape(full_name)}:\*\s*\n\s*\n?'
                                                    content_from_payload = re.sub(signature_pattern_asterisk, '', content_from_payload, flags=re.IGNORECASE)
                                            
                                            # ✅ NOVO: Adicionar assinatura no formato "Nome disse:" para o banco
                                            # ✅ CRÍTICO: Verificar se message.content já tem "disse:" (foi salvo anteriormente)
                                            # Se já tem, apenas substituir o conteúdo após "disse:", não adicionar novamente
                                            if sender and (sender.first_name or sender.last_name):
                                                full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                                                if full_name and content_from_payload:
                                                    # Verificar se message.content já tem formato "Nome disse:"
                                                    existing_signature_pattern = rf'^{re.escape(full_name)}\s+disse:\s*\n*\s*'
                                                    if re.match(existing_signature_pattern, message.content, flags=re.IGNORECASE):
                                                        # Já tem assinatura, apenas substituir o conteúdo após "disse:"
                                                        content_to_save = re.sub(
                                                            existing_signature_pattern,
                                                            rf'{full_name} disse:\n\n',
                                                            message.content,
                                                            flags=re.IGNORECASE,
                                                            count=1
                                                        )
                                                        # Substituir apenas o conteúdo após "disse:" pelo novo conteúdo (com telefones)
                                                        content_after_signature = re.sub(existing_signature_pattern, '', content_to_save, flags=re.IGNORECASE, count=1)
                                                        content_to_save = f"{full_name} disse:\n\n{content_from_payload}"
                                                    else:
                                                        # Não tem assinatura ainda, adicionar
                                                        content_to_save = f"{full_name} disse:\n\n{content_from_payload}"
                                                else:
                                                    content_to_save = content_from_payload
                                            else:
                                                content_to_save = content_from_payload
                                            
                                            # ✅ CORREÇÃO: Atualizar apenas se conteúdo mudou (substituição de nomes)
                                            # Formato no banco: "Nome disse:\n\n{mensagem com telefones}"
                                            if content_to_save != message.content:
                                                from channels.db import database_sync_to_async
                                                from django.db import close_old_connections
                                                message.content = content_to_save  # ✅ Com formato "disse:"
                                                close_old_connections()
                                                await database_sync_to_async(message.save)(update_fields=['content'])
                                                logger.info(f"✅ [CHAT ENVIO] Conteúdo da mensagem atualizado no banco (com formato 'disse:')")
                                                logger.info(f"   Antes: {message.content[:100] if message.content else 'N/A'}...")
                                                logger.info(f"   Depois: {content_to_save[:100]}...")
                                        else:
                                            logger.warning(f"⚠️ [CHAT ENVIO] Nenhuma substituição realizada no texto")
                                            logger.warning(f"   Texto original: {text_before[:200]}")
                                            logger.warning(f"   Mapeamentos disponíveis: {list(name_to_phone_map.keys())}")
                                    else:
                                        logger.warning(f"⚠️ [CHAT ENVIO] Nenhum mapeamento nome->telefone criado para substituição")
                            else:
                                logger.warning(f"⚠️ [CHAT ENVIO] Nenhuma menção válida após normalização")
                        else:
                            logger.warning(f"⚠️ [CHAT ENVIO] Nenhuma menção válida após processamento")
                
                # ✅ SIMPLIFICAÇÃO: Sempre usar /message/sendText com 'quoted' no root quando for reply
                # O endpoint /message/reply pode não existir, então vamos sempre usar o formato padrão
                # O payload já tem 'quoted' adicionado quando é reply (feito acima)
                is_reply = 'quoted' in payload
                logger.info(f"🔍 [CHAT ENVIO] Verificando se é reply:")
                logger.info(f"   É reply? {is_reply}")
                logger.info(f"   quoted_message_id: {_mask_digits(quoted_message_id) if quoted_message_id else 'N/A'}")
                logger.info(f"   quoted_remote_jid: {_mask_remote_jid(quoted_remote_jid) if quoted_remote_jid else 'N/A'}")
                logger.info(f"   original_message: {'Sim' if original_message else 'N/A'}")
                logger.info(f"   Payload tem 'quoted'? {'Sim' if is_reply else 'Não'}")
                
                # ✅ DECISÃO: Se for reply, usar sempre /message/sendText com payload que já tem 'quoted'
                # Não tentar /message/reply primeiro (endpoint pode não existir)
                # ✅ SIMPLIFICAÇÃO: Sempre usar /message/sendText (com ou sem 'quoted')
                # O payload já está pronto (com 'quoted' se for reply, sem se for mensagem normal)
                endpoint = f"{base_url}/message/sendText/{instance.instance_name}"
                
                if is_reply:
                    logger.info(f"💬 [CHAT ENVIO] Enviando mensagem COM REPLY para Evolution API...")
                    logger.info(f"   Endpoint: {endpoint}")
                    logger.info(f"   Reply to: {_mask_digits(quoted_message_id)}")
                    logger.info(f"   RemoteJid: {_mask_remote_jid(quoted_remote_jid)}")
                    logger.info(f"   Participant: {_mask_remote_jid(quoted_participant) if quoted_participant else 'N/A'}")
                else:
                    logger.info(f"📤 [CHAT ENVIO] Enviando mensagem de texto normal para Evolution API...")
                
                logger.info(f"   Tipo: {conversation.conversation_type}")
                logger.info(f"   Número final: {_mask_remote_jid(final_number)}")
                logger.info(f"   Tamanho do texto: {len(content)} caracteres")
                logger.info("   Text (primeiros 100 chars): %s", _truncate_text(content, 100))
                
                # ✅ DEBUG: Verificar se payload tem menções
                if 'mentions' in payload:
                    logger.critical(f"✅ [CHAT ENVIO] Payload TEM menções:")
                    logger.critical(f"   mentions: {json.dumps(payload['mentions'], ensure_ascii=False)}")
                else:
                    logger.warning(f"⚠️ [CHAT ENVIO] Payload NÃO TEM menções (pode estar correto se não houver menções)")
                
                logger.info("   Payload (mascado): %s", mask_sensitive_data(payload))
                logger.info("   Payload (JSON formatado): %s", json.dumps(mask_sensitive_data(payload), indent=2, ensure_ascii=False))
                
                request_start = time.perf_counter()
                response = await client.post(
                    endpoint,
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
                
                logger.critical(f"📥 [CHAT ENVIO] ====== RESPOSTA DA EVOLUTION API ======")
                logger.critical(f"   Status: {response.status_code}")
                logger.critical(f"   Body completo: {response.text}")
                
                # ✅ LOG CRÍTICO: Verificar se a resposta indica sucesso
                if response.status_code in (200, 201):
                    try:
                        response_data = response.json() if response.text else {}
                        logger.critical(f"✅ [CHAT ENVIO] Mensagem enviada com SUCESSO!")
                        logger.critical(f"   Response data: {mask_sensitive_data(response_data)}")
                        
                        # Verificar se retornou message_id
                        evolution_message_id = extract_evolution_message_id(response_data)
                        if evolution_message_id:
                            logger.critical(f"✅ [CHAT ENVIO] Evolution retornou message_id: {_mask_digits(evolution_message_id)}")
                        else:
                            logger.warning(f"⚠️ [CHAT ENVIO] Evolution não retornou message_id na resposta")
                    except Exception as e:
                        logger.warning(f"⚠️ [CHAT ENVIO] Erro ao parsear resposta JSON: {e}")
                else:
                    logger.error(f"❌ [CHAT ENVIO] Erro ao enviar mensagem! Status: {response.status_code}")
                    logger.error(f"   Response: {response.text[:500]}")
                
                # ✅ CORREÇÃO: Tratar erros específicos da Evolution API antes de fazer raise_for_status
                # ✅ FIX: 201 (Created) também é sucesso, não erro!
                # ✅ FIX: Se for resposta e retornar 404, já foi tratado no fallback acima
                if response.status_code not in (200, 201):
                    # Se for 404 e já tentamos o fallback, logar erro
                    if response.status_code == 404 and quoted_message_id:
                        logger.error(f"❌ [CHAT ENVIO] Erro 404 mesmo após fallback. Endpoint pode não existir.")
                    logger.error(f"❌ [CHAT ENVIO] Erro {response.status_code} ao enviar mensagem:")
                    # Payload sempre é o mesmo (já tem 'quoted' se for reply)
                    logger.error(f"   Payload enviado (mascado): {mask_sensitive_data(payload)}")
                    logger.error(f"   Resposta completa: {response.text}")
                    logger.error(f"   Headers enviados: {dict(headers)}")
                elif response.status_code == 201:
                    logger.info(f"✅ [CHAT ENVIO] Mensagem criada com sucesso (201 Created)")
                    logger.info(f"   Payload enviado (mascado): {mask_sensitive_data(payload)}")
                    logger.info(f"   Resposta completa: {response.text}")
                    
                    # ✅ CORREÇÃO CRÍTICA: Erros 500/503 são temporários - fazer retry
                    if response.status_code >= 500:
                        error_msg = f'Erro temporário do servidor (HTTP {response.status_code}): {response.text[:200]}'
                        log.warning(
                            "⏳ [CHAT ENVIO] Erro temporário do servidor (HTTP %s). Reagendando para retry.",
                            response.status_code
                        )
                        raise InstanceTemporarilyUnavailable(
                            instance.instance_name,
                            {'http_status': response.status_code, 'error': error_msg},
                            compute_backoff(retry_count)
                        )
                    
                    # Tentar parsear resposta para identificar erro específico
                    try:
                        error_data = response.json()
                        error_message = error_data.get('response', {}).get('message', [])
                        
                        # Verificar se é erro de número não existe
                        if isinstance(error_message, list) and len(error_message) > 0:
                            first_error = error_message[0]
                            if isinstance(first_error, dict):
                                exists = first_error.get('exists', True)
                                jid = first_error.get('jid', '')
                                number = first_error.get('number', '')
                                
                                if exists is False:
                                    # Número não existe no WhatsApp
                                    message.status = 'failed'
                                    message.error_message = f'Número não está registrado no WhatsApp: {_mask_remote_jid(number)}'
                                    from django.db import close_old_connections
                                    close_old_connections()
                                    await database_sync_to_async(message.save)(update_fields=['status', 'error_message'])
                                    await database_sync_to_async(_broadcast_message_failed)(message.id)
                                    logger.error(f"❌ [CHAT ENVIO] Número não existe no WhatsApp: {_mask_remote_jid(number)}")
                                    return  # Não fazer raise, já tratamos o erro
                    except (ValueError, KeyError, TypeError):
                        # Se não conseguir parsear, continuar com raise_for_status normal
                        pass
                
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
                        from django.db import close_old_connections
                        close_old_connections()
                        await database_sync_to_async(message.save)(update_fields=['message_id'])
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
        from django.db import close_old_connections
        close_old_connections()
        await database_sync_to_async(message.save)(update_fields=['status', 'evolution_status'])
        
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
        
        # ✅ CORREÇÃO CRÍTICA: Enviar conversation_updated para atualizar lista de conversas
        # Isso garante que a última mensagem apareça na lista e a conversa suba para o topo
        # Como estamos em função async, usar database_sync_to_async para chamar broadcast_conversation_updated
        from apps.chat.utils.websocket import broadcast_conversation_updated
        from channels.db import database_sync_to_async
        
        try:
            # ✅ FIX CRÍTICO: Usar broadcast_conversation_updated que já faz prefetch de last_message
            # Passar message_id para garantir que a mensagem recém-criada seja incluída
            # Como broadcast_conversation_updated é síncrono, precisamos chamar via database_sync_to_async
            await database_sync_to_async(broadcast_conversation_updated)(
                message.conversation, 
                message_id=str(message.id)
            )
            logger.info(f"📡 [CHAT ENVIO] conversation_updated enviado para atualizar lista de conversas")
        except Exception as e:
            logger.error(f"❌ [CHAT ENVIO] Erro no broadcast conversation_updated: {e}", exc_info=True)
        
        logger.info(f"✅ [CHAT ENVIO] Mensagem enviada e broadcast com sucesso!")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Phone: {message.conversation.contact_phone}")
        logger.info(f"   Status: {message.status}")
        logger.info(f"   Broadcast: message_received + message_status_update + conversation_updated")

        record_latency(
            'send_message_total',
            time.perf_counter() - overall_start,
            {
                'message_id': str(message.id),
                'conversation_id': str(conversation.id),
                'attachments': len(attachment_urls),
            }
        )
    
    except InstanceTemporarilyUnavailable:
        # ✅ Re-raise para ser tratado pelo stream_consumer
        raise
    except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.NetworkError) as e:
        # ✅ CORREÇÃO CRÍTICA: Erros de rede/timeout são temporários - fazer retry
        # Tentar obter instance_name do contexto (pode não estar disponível se erro ocorreu antes)
        try:
            instance_name = instance.instance_name if 'instance' in locals() and instance else 'unknown'
        except:
            instance_name = 'unknown'
        log.warning(
            "⏳ [CHAT ENVIO] Erro de rede/timeout (%s). Reagendando para retry.",
            type(e).__name__
        )
        raise InstanceTemporarilyUnavailable(
            instance_name,
            {'error_type': type(e).__name__, 'error': str(e)},
            compute_backoff(retry_count)
        )
    except Exception as e:
        logger.error(f"❌ [CHAT] Erro ao enviar mensagem {message_id}: {e}", exc_info=True)
        record_error('send_message', str(e))
        
        # Marca como falha apenas se não for erro temporário
        try:
            from django.db import close_old_connections
            close_old_connections()
            message.status = 'failed'
            message.error_message = str(e)
            await database_sync_to_async(message.save)(update_fields=['status', 'error_message'])
            await database_sync_to_async(_broadcast_message_failed)(message_id)
        except Exception:
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
    from channels.db import database_sync_to_async
    from django.db import close_old_connections
    import httpx
    
    logger.critical(f"📸 [PROFILE PIC] Buscando foto de perfil...")
    logger.critical(f"   Conversation ID: {conversation_id}")
    logger.critical(f"   Phone recebido: {phone}")
    
    try:
        # ✅ CORREÇÃO CRÍTICA: Fechar conexões antigas antes de operações de banco
        close_old_connections()
        
        # ✅ CORREÇÃO: Tratar caso de conversa não existir (pode ter sido deletada)
        # ✅ CORREÇÃO: Usar database_sync_to_async em vez de sync_to_async para gerenciar conexões corretamente
        try:
            conversation = await database_sync_to_async(
                Conversation.objects.select_related('tenant').get
            )(id=conversation_id)
        except Conversation.DoesNotExist:
            logger.critical(f"⚠️ [PROFILE PIC] Conversa não encontrada (pode ter sido deletada): {conversation_id}")
            logger.critical(f"   Phone: {phone}")
            return  # ✅ Retornar silenciosamente - conversa não existe mais
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar conversation_type ANTES de processar
        logger.critical(f"🔍 [PROFILE PIC] Validação crítica da conversa:")
        logger.critical(f"   Conversation ID: {conversation.id}")
        logger.critical(f"   Conversation Type: {conversation.conversation_type}")
        logger.critical(f"   Contact Phone: {conversation.contact_phone}")
        logger.critical(f"   Contact Name: {conversation.contact_name}")
        logger.critical(f"   Phone recebido: {phone}")
        
        # ✅ GARANTIA: Apenas processar contatos individuais (não grupos)
        if conversation.conversation_type == 'group':
            logger.critical(f"❌ [PROFILE PIC] ERRO CRÍTICO: Tentativa de buscar foto de grupo como individual!")
            logger.critical(f"   Conversation ID: {conversation_id}")
            logger.critical(f"   Conversation Type: {conversation.conversation_type}")
            logger.critical(f"   Contact Phone: {conversation.contact_phone}")
            logger.critical(f"   Phone recebido: {phone}")
            logger.critical(f"   ⚠️ ISSO PODE CAUSAR CONFUSÃO ENTRE CONTATO E GRUPO!")
            return
        
        # ✅ VALIDAÇÃO ADICIONAL: Verificar se contact_phone corresponde ao phone recebido
        # Se não corresponder, pode ser que a conversa foi atualizada incorretamente
        contact_phone_clean = conversation.contact_phone.replace('+', '').replace('@s.whatsapp.net', '').replace('@g.us', '')
        phone_clean = phone.replace('+', '').replace('@s.whatsapp.net', '').replace('@g.us', '')
        
        if contact_phone_clean != phone_clean:
            logger.critical(f"⚠️ [PROFILE PIC] AVISO: Phone recebido não corresponde ao contact_phone da conversa!")
            logger.critical(f"   Contact Phone (clean): {contact_phone_clean}")
            logger.critical(f"   Phone recebido (clean): {phone_clean}")
            logger.critical(f"   ⚠️ Continuando mesmo assim, mas pode haver confusão...")
        
        # Busca instância WhatsApp ativa
        from django.db.models import Q
        from apps.notifications.models import WhatsAppInstance
        from apps.connections.models import EvolutionConnection
        
        # ✅ CORREÇÃO: Fechar conexões antigas antes de nova operação de banco
        close_old_connections()
        
        # ✅ CRÍTICO: Preferir instância da conversa (que recebeu a mensagem)
        wa_instance = None
        if conversation.instance_name and str(conversation.instance_name).strip():
            wa_instance = await database_sync_to_async(
                lambda: WhatsAppInstance.objects.filter(
                    Q(instance_name=conversation.instance_name.strip()) | Q(evolution_instance_name=conversation.instance_name.strip()),
                    tenant=conversation.tenant, is_active=True, status='active'
                ).first()
            )()
        if not wa_instance:
            wa_instance = await database_sync_to_async(
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
        # ✅ CORREÇÃO: Fechar conexões antigas antes de nova operação de banco
        close_old_connections()
        
        evolution_server = await database_sync_to_async(
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
        # ✅ CRÍTICO: Usar instance da conversa (instância que tem o contato)
        instance_name = (conversation.instance_name and str(conversation.instance_name).strip()) or wa_instance.instance_name
        
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
                        # ✅ CORREÇÃO: NÃO usar pushname - apenas name do contato cadastrado
                        # Se não tiver name, buscar na lista de contatos ou usar telefone formatado
                        api_name = contact_info.get('name', '').strip() if contact_info.get('name') else ''
                        pushname = contact_info.get('pushname', '').strip() if contact_info.get('pushname') else ''
                        
                        logger.info(f"🔍 [PROFILE PIC] Nome da API: '{api_name}' | PushName: '{pushname}' (exists: {contact_info.get('exists', False)})")
                        
                        # ✅ PRIORIDADE: 1) Nome do contato cadastrado na lista, 2) name da API (se exists=True), 3) Telefone formatado
                        # NUNCA usar pushname para exibição - apenas como sugestão no cadastro
                        from apps.contacts.models import Contact
                        from django.db.models import Q
                        from apps.contacts.signals import normalize_phone_for_search
                        
                        normalized_phone = normalize_phone_for_search(clean_phone)
                        # ✅ CORREÇÃO: Fechar conexões antigas antes de nova operação de banco
                        close_old_connections()
                        # ✅ CORREÇÃO: Usar database_sync_to_async para query em contexto assíncrono
                        saved_contact = await database_sync_to_async(
                            Contact.objects.filter(
                                Q(tenant=conversation.tenant) &
                                (Q(phone=normalized_phone) | Q(phone=clean_phone))
                            ).first
                        )()
                        
                        if saved_contact:
                            # ✅ Contato cadastrado - usar nome da lista
                            contact_name = saved_contact.name
                            logger.info(f"✅ [PROFILE PIC] Usando nome da lista de contatos: '{contact_name}'")
                        elif api_name and contact_info.get('exists', False):
                            # ✅ Contato existe no WhatsApp mas não está cadastrado - usar name da API
                            contact_name = api_name
                            logger.info(f"✅ [PROFILE PIC] Usando name da API (contato existe no WhatsApp): '{contact_name}'")
                        else:
                            # ✅ Contato não cadastrado e não existe no WhatsApp - usar telefone formatado
                            contact_name = _format_phone_for_display(clean_phone)
                            logger.info(f"📞 [PROFILE PIC] Contato não cadastrado - usando telefone formatado: '{contact_name}'")
                            logger.info(f"   ℹ️ PushName disponível como sugestão: '{pushname}' (não será salvo)")
                        
                        # Atualizar se mudou
                        if contact_name and conversation.contact_name != contact_name:
                            old_name = conversation.contact_name
                            conversation.contact_name = contact_name
                            update_fields.append('contact_name')
                            logger.info(f"✅ [PROFILE PIC] Nome atualizado: '{old_name}' → '{contact_name}'")
                        else:
                            logger.info(f"ℹ️ [PROFILE PIC] Nome não mudou: '{conversation.contact_name}'")
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
                # ✅ CORREÇÃO: Fechar conexões antigas antes de salvar
                close_old_connections()
                await database_sync_to_async(conversation.save)(update_fields=update_fields)
                logger.info(f"✅ [PROFILE PIC] Atualizações salvas: {', '.join(update_fields)}")
                
                # ✅ CRÍTICO: Sempre fazer broadcast se houver atualizações (foto OU nome)
                # Isso garante que o frontend recebe atualizações mesmo se só o nome mudou
                try:
                    from apps.chat.utils.serialization import serialize_conversation_for_ws_async
                    
                    # ✅ IMPORTANTE: Recarregar conversa do banco para garantir dados atualizados
                    # ✅ CORREÇÃO: Fechar conexões antigas antes de recarregar
                    close_old_connections()
                    await database_sync_to_async(conversation.refresh_from_db)()
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
    from channels.db import database_sync_to_async
    from django.db import close_old_connections
    import httpx
    
    logger.info(f"👤 [CONTACT NAME] Buscando nome de contato...")
    logger.info(f"   Conversation ID: {conversation_id}")
    logger.info(f"   Phone: {phone}")
    
    try:
        # ✅ CORREÇÃO CRÍTICA: Fechar conexões antigas antes de operações de banco
        close_old_connections()
        
        # ✅ CORREÇÃO: Tratar caso de conversa não existir (pode ter sido deletada)
        try:
            conversation = await database_sync_to_async(
                Conversation.objects.select_related('tenant').get
            )(id=conversation_id)
        except Conversation.DoesNotExist:
            logger.warning(f"⚠️ [CONTACT NAME] Conversa não encontrada (pode ter sido deletada): {conversation_id}")
            logger.warning(f"   Phone: {phone}")
            return  # ✅ Retornar silenciosamente - conversa não existe mais
        
        # ✅ GARANTIA: Apenas processar contatos individuais (não grupos)
        if conversation.conversation_type == 'group':
            logger.info(f"⏭️ [CONTACT NAME] Pulando grupo (não processa grupos): {conversation_id}")
            return
        
        # ✅ CRÍTICO: Usar instance da conversa (instância que tem o contato)
        instance_name_for_api = (conversation.instance_name and str(conversation.instance_name).strip()) or instance_name
        instance_name = instance_name_for_api
        
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
                            # ✅ CORREÇÃO: NÃO usar pushname - apenas name do contato cadastrado
                            # Se não tiver name, buscar na lista de contatos ou usar telefone formatado
                            api_name = contact_info.get('name', '').strip() if contact_info.get('name') else ''
                            pushname = contact_info.get('pushname', '').strip() if contact_info.get('pushname') else ''
                            
                            logger.info(f"🔍 [CONTACT NAME] Nome da API: '{api_name}' | PushName: '{pushname}' (exists: {contact_info.get('exists', False)})")
                            
                            # ✅ PRIORIDADE: 1) Nome do contato cadastrado na lista, 2) name da API (se exists=True), 3) Telefone formatado
                            # NUNCA usar pushname para exibição - apenas como sugestão no cadastro
                            from apps.contacts.models import Contact
                            from django.db.models import Q
                            from apps.contacts.signals import normalize_phone_for_search
                            
                            normalized_phone = normalize_phone_for_search(clean_phone)
                            from django.db import close_old_connections
                            close_old_connections()
                            saved_contact = await database_sync_to_async(
                                Contact.objects.filter(
                                    Q(tenant=conversation.tenant) &
                                    (Q(phone=normalized_phone) | Q(phone=clean_phone))
                                ).first
                            )()
                            
                            if saved_contact:
                                # ✅ Contato cadastrado - usar nome da lista
                                contact_name = saved_contact.name
                                logger.info(f"✅ [CONTACT NAME] Usando nome da lista de contatos: '{contact_name}'")
                            elif api_name and contact_info.get('exists', False):
                                # ✅ Contato existe no WhatsApp mas não está cadastrado - usar name da API
                                contact_name = api_name
                                logger.info(f"✅ [CONTACT NAME] Usando name da API (contato existe no WhatsApp): '{contact_name}'")
                            else:
                                # ✅ Contato não cadastrado e não existe no WhatsApp - usar telefone formatado
                                contact_name = _format_phone_for_display(clean_phone)
                                logger.info(f"📞 [CONTACT NAME] Contato não cadastrado - usando telefone formatado: '{contact_name}'")
                                logger.info(f"   ℹ️ PushName disponível como sugestão: '{pushname}' (não será salvo)")
                            
                            # Atualizar se mudou
                            if contact_name and conversation.contact_name != contact_name:
                                from django.db import close_old_connections
                                close_old_connections()
                                old_name = conversation.contact_name
                                conversation.contact_name = contact_name
                                await database_sync_to_async(conversation.save)(update_fields=['contact_name'])
                                
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
                                logger.info(f"ℹ️ [CONTACT NAME] Nome não mudou: '{conversation.contact_name}'")
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


async def handle_edit_message(message_id: str, new_content: str, edited_by_id: int = None, retry_count: int = 0):
    """
    Handler: Edita mensagem enviada via Evolution API.
    
    Validações:
    - Mensagem deve ser outgoing (enviada pela aplicação)
    - Mensagem deve ter message_id (foi enviada com sucesso)
    - Mensagem deve ser de texto (não mídia)
    - Deve ter menos de 15 minutos desde o envio
    - Novo conteúdo não pode estar vazio
    """
    from apps.chat.models import Message, MessageEditHistory
    from apps.notifications.models import WhatsAppInstance
    from apps.connections.models import EvolutionConnection
    from channels.layers import get_channel_layer
    from channels.db import database_sync_to_async
    from django.db import close_old_connections
    import httpx
    from datetime import timedelta
    
    logger.info(f"✏️ [EDIT MESSAGE] Iniciando edição de mensagem: {message_id}")
    
    try:
        # ✅ CORREÇÃO CRÍTICA: Fechar conexões antigas antes de operações de banco
        close_old_connections()
        
        # Buscar mensagem
        message = await database_sync_to_async(
            Message.objects.select_related(
                'conversation',
                'conversation__tenant',
                'sender'
            ).prefetch_related('attachments').get
        )(id=message_id)
        
        # ✅ VALIDAÇÃO 1: Mensagem deve ser outgoing
        if message.direction != 'outgoing':
            logger.error(f"❌ [EDIT MESSAGE] Mensagem não é outgoing: {message.direction}")
            raise ValueError("Apenas mensagens enviadas pela aplicação podem ser editadas")
        
        # ✅ VALIDAÇÃO 2: Mensagem deve ter message_id
        if not message.message_id:
            logger.error(f"❌ [EDIT MESSAGE] Mensagem sem message_id (não foi enviada com sucesso)")
            raise ValueError("Mensagem não foi enviada com sucesso")
        
        # ✅ VALIDAÇÃO 3: Mensagem deve ser de texto (não mídia)
        close_old_connections()
        attachments = await database_sync_to_async(list)(message.attachments.all())
        if attachments:
            logger.error(f"❌ [EDIT MESSAGE] Mensagem tem anexos, não pode ser editada")
            raise ValueError("Mensagens com anexos não podem ser editadas")
        
        # ✅ VALIDAÇÃO 4: Deve ter menos de 15 minutos desde o envio
        time_since_sent = timezone.now() - message.created_at
        if time_since_sent > timedelta(minutes=15):
            logger.error(f"❌ [EDIT MESSAGE] Mensagem tem mais de 15 minutos: {time_since_sent}")
            raise ValueError("Mensagens só podem ser editadas até 15 minutos após o envio")
        
        # ✅ VALIDAÇÃO 5: Novo conteúdo não pode estar vazio
        new_content = new_content.strip()
        if not new_content:
            logger.error(f"❌ [EDIT MESSAGE] Novo conteúdo está vazio")
            raise ValueError("Novo conteúdo não pode estar vazio")
        
        # ✅ VALIDAÇÃO 6: Novo conteúdo deve ser diferente do atual
        if new_content == message.content:
            logger.warning(f"⚠️ [EDIT MESSAGE] Novo conteúdo é igual ao atual")
            return  # Não precisa editar se é igual
        
        old_content = message.content
        
        logger.info(f"✅ [EDIT MESSAGE] Validações passadas:")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Evolution Message ID: {message.message_id}")
        logger.info(f"   Conteúdo antigo: {old_content[:100]}...")
        logger.info(f"   Conteúdo novo: {new_content[:100]}...")
        logger.info(f"   Tempo desde envio: {time_since_sent}")
        
        # Buscar instância WhatsApp
        close_old_connections()
        instance = await database_sync_to_async(
            WhatsAppInstance.objects.filter(
                tenant=message.conversation.tenant,
                is_active=True,
                status='active'
            ).first
        )()
        
        if not instance:
            logger.error(f"❌ [EDIT MESSAGE] Nenhuma instância WhatsApp ativa")
            raise ValueError("Nenhuma instância WhatsApp ativa")
        
        # Meta Cloud API não expõe endpoint de edição de mensagem; apenas Evolution suporta
        if getattr(instance, 'integration_type', None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            logger.warning(f"⚠️ [EDIT MESSAGE] Edição não suportada para instância Meta (message_id=%s)", message.id)
            raise ValueError("Edição de mensagem não é suportada para conexão Meta (WhatsApp Cloud API).")
        
        # Buscar servidor Evolution
        close_old_connections()
        evolution_server = await database_sync_to_async(
            EvolutionConnection.objects.filter(is_active=True).first
        )()
        
        if not evolution_server and not instance.api_url:
            logger.error(f"❌ [EDIT MESSAGE] Configuração da Evolution API não encontrada")
            raise ValueError("Configuração da Evolution API não encontrada")
        
        # Preparar URL e credenciais
        base_url = (instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = instance.api_key or evolution_server.api_key
        instance_name = instance.instance_name
        
        # Preparar remoteJid
        if message.conversation.conversation_type == 'group':
            remote_jid = message.conversation.contact_phone
            if not remote_jid.endswith('@g.us'):
                if remote_jid.endswith('@s.whatsapp.net'):
                    remote_jid = remote_jid.replace('@s.whatsapp.net', '@g.us')
                else:
                    remote_jid = f"{remote_jid.rstrip('@')}@g.us"
        else:
            phone = message.conversation.contact_phone
            if phone.endswith('@s.whatsapp.net'):
                remote_jid = phone
            else:
                phone_clean = phone.lstrip('+')
                remote_jid = f"{phone_clean}@s.whatsapp.net"
        
        # ✅ NOVO: Processar menções se for grupo e o conteúdo tiver menções
        processed_content = new_content
        mentions_payload = None
        
        if message.conversation.conversation_type == 'group':
            # Extrair menções do conteúdo (formato @número ou @nome)
            import re
            mentioned_numbers_in_text = re.findall(r'@(\d+)', new_content)
            mentioned_names_in_text = re.findall(r'@([A-Za-zÀ-ÿ\s\.]+?)(?=\s|$|,|\.|!|\?|:)', new_content)
            
            # Se houver menções, processar similar ao envio normal
            if mentioned_numbers_in_text or mentioned_names_in_text:
                logger.info(f"✏️ [EDIT MESSAGE] Processando menções na edição:")
                logger.info(f"   Números encontrados: {len(mentioned_numbers_in_text)}")
                logger.info(f"   Nomes encontrados: {len(mentioned_names_in_text)}")
                
                # Buscar participantes do grupo
                from django.db import close_old_connections
                close_old_connections()
                await database_sync_to_async(message.conversation.refresh_from_db)()
                group_metadata = message.conversation.group_metadata or {}
                group_participants = group_metadata.get('participants', [])
                
                if group_participants:
                    # Buscar contatos cadastrados primeiro
                    from apps.contacts.models import Contact
                    from apps.notifications.services import normalize_phone
                    from apps.contacts.signals import normalize_phone_for_search
                    
                    tenant_id = message.conversation.tenant_id
                    from django.db import close_old_connections
                    close_old_connections()
                    all_contacts = await database_sync_to_async(list)(
                        Contact.objects.filter(
                            tenant_id=tenant_id
                        ).exclude(phone__isnull=True).exclude(phone='').values('phone', 'name')
                    )
                    
                    phone_to_contact = {}
                    for contact in all_contacts:
                        contact_phone_raw = contact.get('phone', '').strip()
                        if contact_phone_raw:
                            normalized_contact_phone = normalize_phone(contact_phone_raw)
                            if normalized_contact_phone:
                                contact_name = contact.get('name', '').strip()
                                if contact_name:
                                    phone_to_contact[normalized_contact_phone] = contact_name
                    
                    # Criar mapas para busca rápida
                    participants_by_name = {}
                    participants_by_phone = {}
                    
                    for p in group_participants:
                        participant_name = (p.get('name') or '').strip().lower()
                        participant_phone_number = p.get('phoneNumber') or p.get('phone_number', '')
                        
                        if participant_name:
                            participants_by_name[participant_name] = p
                        
                        if participant_phone_number:
                            phone_raw = participant_phone_number.split('@')[0]
                            if phone_raw:
                                normalized = normalize_phone(phone_raw)
                                if normalized:
                                    participants_by_phone[normalized] = p
                                    participants_by_phone[normalize_phone_for_search(normalized)] = p
                                phone_clean = phone_raw.replace('+', '').replace(' ', '').replace('-', '').strip()
                                if phone_clean:
                                    participants_by_phone[phone_clean] = p
                    
                    # Processar menções e criar array de números
                    mention_phones = []
                    name_to_phone_map = {}
                    
                    # Processar números já no formato @número
                    for num in mentioned_numbers_in_text:
                        num_clean = num.lstrip('+')
                        num_clean = ''.join(filter(str.isdigit, num_clean))
                        if num_clean and len(num_clean) >= 10:
                            mention_phones.append(num_clean)
                    
                    # Processar nomes (@nome) e converter para números
                    for name_match in mentioned_names_in_text:
                        name = name_match.strip()
                        name_lower = name.lower()
                        
                        matched_phone = None
                        
                        # Buscar em contatos cadastrados primeiro
                        for contact_phone, contact_name in phone_to_contact.items():
                            if contact_name.lower() == name_lower:
                                matched_phone = contact_phone.lstrip('+')
                                matched_phone = ''.join(filter(str.isdigit, matched_phone))
                                name_to_phone_map[name] = matched_phone
                                break
                        
                        # Se não encontrou, buscar em participantes do grupo
                        if not matched_phone and name_lower in participants_by_name:
                            participant = participants_by_name[name_lower]
                            participant_phone_number = participant.get('phoneNumber') or participant.get('phone_number', '')
                            if participant_phone_number:
                                phone_raw = participant_phone_number.split('@')[0]
                                if phone_raw:
                                    matched_phone = phone_raw.lstrip('+')
                                    matched_phone = ''.join(filter(str.isdigit, matched_phone))
                                    name_to_phone_map[name] = matched_phone
                        
                        if matched_phone and len(matched_phone) >= 10:
                            if matched_phone not in mention_phones:
                                mention_phones.append(matched_phone)
                    
                    # Substituir nomes por telefones no conteúdo
                    if name_to_phone_map:
                        sorted_names = sorted(name_to_phone_map.items(), key=lambda x: len(x[0]), reverse=True)
                        for name, phone in sorted_names:
                            escaped_name = re.escape(name)
                            pattern = rf'@{escaped_name}(?=\s|$|,|\.|!|\?|:)'
                            replacement = f'@{phone}'
                            processed_content = re.sub(pattern, replacement, processed_content, flags=re.IGNORECASE)
                            logger.info(f"   ✅ Substituído: '@{name}' -> '@{_mask_digits(phone)}'")
                    
                    # Criar payload de menções se houver números
                    if mention_phones:
                        mentions_payload = {
                            'everyOne': False,
                            'mentioned': mention_phones
                        }
                        logger.info(f"✅ [EDIT MESSAGE] {len(mention_phones)} menção(ões) processada(s)")
        
        # Preparar payload para Evolution API
        # Documentação: https://www.postman.com/agenciadgcode/evolution-api/request/xxxxx/edit-message
        payload = {
            'key': {
                'remoteJid': remote_jid,
                'fromMe': True,
                'id': message.message_id
            },
            'message': {
                'conversation': processed_content  # ✅ Usar conteúdo processado (com telefones ao invés de nomes)
            }
        }
        
        # ✅ NOVO: Adicionar menções ao payload se houver
        if mentions_payload:
            payload['mentions'] = mentions_payload
        
        # Se for grupo, adicionar participant
        if message.conversation.conversation_type == 'group':
            # Buscar participant do metadata ou do sender_phone
            participant = None
            if message.metadata and isinstance(message.metadata, dict):
                participant = message.metadata.get('participant')
            
            if not participant and message.sender_phone:
                # Tentar construir participant do sender_phone
                phone_clean = message.sender_phone.lstrip('+')
                participant = f"{phone_clean}@s.whatsapp.net"
            
            if participant:
                payload['key']['participant'] = participant
        
        headers = {
            'Content-Type': 'application/json',
            'apikey': api_key
        }
        
        endpoint = f"{base_url}/message/editMessage/{instance_name}"
        
        logger.info(f"✏️ [EDIT MESSAGE] Enviando edição para Evolution API...")
        logger.info(f"   Endpoint: {endpoint}")
        logger.info(f"   RemoteJid: {_mask_remote_jid(remote_jid)}")
        logger.info(f"   Message ID: {_mask_digits(message.message_id)}")
        
        # Enviar para Evolution API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            
            if response.status_code in (200, 201):
                logger.info(f"✅ [EDIT MESSAGE] Mensagem editada com sucesso!")
                
                # Salvar histórico de edição
                close_old_connections()
                edit_history = await database_sync_to_async(MessageEditHistory.objects.create)(
                    message=message,
                    old_content=old_content,
                    new_content=new_content,
                    edited_by_id=edited_by_id,
                    evolution_message_id=message.message_id,
                    metadata={'response_status': response.status_code}
                )
                
                # ✅ CORREÇÃO: Atualizar conteúdo da mensagem no banco com conteúdo processado (com telefones)
                # Isso garante que o frontend mostre o texto correto (com números ao invés de nomes)
                message.content = processed_content
                message.is_edited = True
                close_old_connections()
                await database_sync_to_async(message.save)(update_fields=['content', 'is_edited'])
                
                logger.info(f"✅ [EDIT MESSAGE] Histórico de edição salvo: {edit_history.id}")
                
                # Broadcast via WebSocket
                channel_layer = get_channel_layer()
                if channel_layer:
                    conversation_id = str(message.conversation_id)
                    room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{conversation_id}"
                    
                    # Serializar mensagem atualizada
                    from apps.chat.utils.serialization import serialize_message_for_ws
                    message_data = await database_sync_to_async(serialize_message_for_ws)(message)
                    
                    await channel_layer.group_send(
                        room_group_name,
                        {
                            'type': 'message_edited',
                            'message': message_data,
                            'conversation_id': conversation_id
                        }
                    )
                    
                    logger.info(f"✅ [EDIT MESSAGE] Broadcast WebSocket enviado")
                
                return True
            else:
                error_text = response.text[:500] if response.text else 'Sem resposta'
                logger.error(f"❌ [EDIT MESSAGE] Erro ao editar mensagem: HTTP {response.status_code}")
                logger.error(f"   Resposta: {error_text}")
                raise Exception(f"Evolution API retornou erro: HTTP {response.status_code}")
                
    except Message.DoesNotExist:
        logger.error(f"❌ [EDIT MESSAGE] Mensagem não encontrada: {message_id}")
        raise
    except Exception as e:
        logger.error(f"❌ [EDIT MESSAGE] Erro ao editar mensagem: {e}", exc_info=True)
        raise


async def handle_mark_message_as_read(conversation_id: str, message_id: str, retry_count: int = 0):
    """
    Handler: Envia read receipt para mensagens em background.
    """
    from apps.chat.models import Message
    from channels.db import database_sync_to_async
    from django.db import close_old_connections

    try:
        # ✅ CORREÇÃO CRÍTICA: Fechar conexões antigas antes de operações de banco
        close_old_connections()
        
        message = await database_sync_to_async(
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
        close_old_connections()
        await database_sync_to_async(
            Message.objects.filter(id=message.id).update
        )(status='seen')
        message.status = 'seen'

    from django.db.models import Q
    from apps.notifications.models import WhatsAppInstance

    close_old_connections()
    # ✅ CRÍTICO: Preferir instância da conversa (que recebeu a mensagem)
    wa_instance = None
    if message.conversation.instance_name and str(message.conversation.instance_name).strip():
        wa_instance = await database_sync_to_async(
            lambda: WhatsAppInstance.objects.filter(
                Q(instance_name=message.conversation.instance_name.strip()) | Q(evolution_instance_name=message.conversation.instance_name.strip()),
                tenant=message.conversation.tenant, is_active=True, status='active'
            ).first()
        )()
    if not wa_instance:
        wa_instance = await database_sync_to_async(
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

    # ✅ CORREÇÃO: send_read_receipt acessa banco de dados, usar database_sync_to_async
    from django.db import close_old_connections
    close_old_connections()
    sent = await database_sync_to_async(send_read_receipt)(
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
    Loop de reconexão: em caso de Connection reset / AMQPConnectionError, aguarda backoff e tenta de novo.
    """
    import re
    import os

    rabbitmq_url = settings.RABBITMQ_URL
    safe_url = re.sub(r'://.*@', '://***:***@', rabbitmq_url)

    backoff_sec = 5
    max_backoff = 60
    attempt = 0

    while True:
        try:
            attempt += 1
            logger.info("=" * 80)
            logger.info("🔍 [CHAT CONSUMER] Conectando ao RabbitMQ (tentativa %s): %s", attempt, safe_url)
            logger.info("=" * 80)

            connection = await aio_pika.connect_robust(
                rabbitmq_url,
                heartbeat=0,
                blocked_connection_timeout=0,
                socket_timeout=10,
                retry_delay=1,
                connection_attempts=1
            )
            logger.info("✅ [CHAT CONSUMER] Conexão RabbitMQ estabelecida com sucesso!")
            backoff_sec = 5  # reset backoff após sucesso

            channel = await connection.channel()
            logger.info("✅ [CHAT CONSUMER] Channel criado com sucesso!")

            queue_send = await channel.declare_queue(QUEUE_SEND_MESSAGE, durable=True)
            queue_profile_pic = await channel.declare_queue(QUEUE_FETCH_PROFILE_PIC, durable=True)
            queue_process_incoming_media = await channel.declare_queue(QUEUE_PROCESS_INCOMING_MEDIA, durable=True)
            queue_fetch_group_info = await channel.declare_queue(QUEUE_FETCH_GROUP_INFO, durable=True)
            logger.info("✅ [CHAT CONSUMER] Filas declaradas")

            async def on_send_message(message: aio_pika.IncomingMessage):
                async with message.process():
                    try:
                        payload = json.loads(message.body.decode())
                        await handle_send_message(payload['message_id'])
                    except Exception as e:
                        logger.error(f"❌ [CHAT CONSUMER] Erro send_message: {e}", exc_info=True)

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

            async def on_process_incoming_media(message: aio_pika.IncomingMessage):
                async with message.process():
                    try:
                        from apps.chat.media_tasks import handle_process_incoming_media
                        payload = json.loads(message.body.decode())
                        inst = payload.get('instance_name') or '(vazio)'
                        mid = (payload.get('message_id') or '')[:8]
                        logger.info(f"📥 [CHAT CONSUMER] Recebida task process_incoming_media | instance_name={inst} | message_id={mid}...")
                        retry_count = payload.get('_retry_count', 0)
                        message_key_from_payload = payload.get('message_key')
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
                            mime_type=payload.get('mime_type'),
                            jpeg_thumbnail=payload.get('jpeg_thumbnail'),
                            meta_media_id=payload.get('meta_media_id'),
                        )
                        logger.info(f"✅ [CHAT CONSUMER] process_incoming_media concluída com sucesso")
                    except InstanceTemporarilyUnavailable as e:
                        wait_time = e.wait_seconds or compute_backoff(payload.get('_retry_count', 0))
                        next_retry = payload.get('_retry_count', 0) + 1
                        logger.warning(
                            "⏳ [CHAT CONSUMER] Instância indisponível para process_incoming_media (message=%s). Reagendando em %ss.",
                            payload.get('message_id'), wait_time,
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
                        raise

            async def on_fetch_group_info(message: aio_pika.IncomingMessage):
                async with message.process():
                    try:
                        from apps.chat.media_tasks import handle_fetch_group_info
                        payload = json.loads(message.body.decode())
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
                        raise

            await queue_send.consume(on_send_message)
            await queue_profile_pic.consume(on_fetch_profile_pic)
            await queue_process_incoming_media.consume(on_process_incoming_media)
            await queue_fetch_group_info.consume(on_fetch_group_info)
            logger.info("🚀 [CHAT CONSUMER] Consumers iniciados e aguardando mensagens")
            await asyncio.Future()

        except Exception as e:
            error_msg = str(e)
            if 'ACCESS_REFUSED' in error_msg or 'authentication' in error_msg.lower():
                logger.error("🚨 [CHAT CONSUMER] Erro de autenticação RabbitMQ: %s. Reconectando em %ss.", error_msg[:200], backoff_sec)
            else:
                logger.warning(
                    "⚠️ [CHAT CONSUMER] Conexão RabbitMQ falhou (Connection reset / rede). Reconectando em %ss: %s",
                    backoff_sec, error_msg[:200],
                )
            await asyncio.sleep(backoff_sec)
            backoff_sec = min(backoff_sec * 2, max_backoff)


# Para rodar o consumer
if __name__ == '__main__':
    import asyncio
    asyncio.run(start_chat_consumers())

