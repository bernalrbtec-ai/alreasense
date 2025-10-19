"""
Webhook handler para Evolution API.
Recebe eventos de mensagens e atualiza o banco.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.chat.models import Conversation, Message, MessageAttachment
from apps.chat.tasks import download_attachment
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def evolution_webhook(request):
    """
    Webhook para receber eventos da Evolution API.
    
    Eventos suportados:
    - messages.upsert: Nova mensagem recebida
    - messages.update: Atualização de status (delivered/read)
    """
    try:
        data = request.data
        event_type = data.get('event')
        instance_name = data.get('instance')
        
        logger.info(f"📥 [WEBHOOK] Evento recebido: {event_type} - {instance_name}")
        
        if not instance_name:
            return Response(
                {'error': 'instance é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Busca conexão pelo instance_name
        try:
            connection = EvolutionConnection.objects.select_related('tenant').get(
                instance_name=instance_name
            )
        except EvolutionConnection.DoesNotExist:
            logger.warning(f"⚠️ [WEBHOOK] Conexão não encontrada: {instance_name}")
            return Response(
                {'error': 'Conexão não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Roteamento por tipo de evento
        if event_type == 'messages.upsert':
            handle_message_upsert(data, connection.tenant)
        elif event_type == 'messages.update':
            handle_message_update(data, connection.tenant)
        else:
            logger.info(f"ℹ️ [WEBHOOK] Evento não tratado: {event_type}")
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar webhook: {e}", exc_info=True)
        return Response(
            {'error': 'Erro interno'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@transaction.atomic
def handle_message_upsert(data, tenant):
    """
    Processa evento de nova mensagem (messages.upsert).
    
    Cria ou atualiza:
    - Conversation
    - Message
    - MessageAttachment (se houver)
    """
    logger.info(f"📥 [WEBHOOK UPSERT] Dados recebidos: {data}")
    
    try:
        message_data = data.get('data', {})
        key = message_data.get('key', {})
        message_info = message_data.get('message', {})
        
        # Extrai dados
        remote_jid = key.get('remoteJid', '')  # Ex: 5517999999999@s.whatsapp.net
        from_me = key.get('fromMe', False)
        message_id = key.get('id')
        
        # Telefone (remove @s.whatsapp.net)
        phone = remote_jid.split('@')[0]
        if not phone.startswith('+'):
            phone = '+' + phone
        
        # Tipo de mensagem
        message_type = message_data.get('messageType', 'text')
        
        # Conteúdo
        if message_type == 'conversation':
            content = message_info.get('conversation', '')
        elif message_type == 'extendedTextMessage':
            content = message_info.get('extendedTextMessage', {}).get('text', '')
        elif message_type == 'imageMessage':
            content = message_info.get('imageMessage', {}).get('caption', '')
        elif message_type == 'videoMessage':
            content = message_info.get('videoMessage', {}).get('caption', '')
        elif message_type == 'documentMessage':
            content = message_info.get('documentMessage', {}).get('caption', '')
        elif message_type == 'audioMessage':
            content = '[Áudio]'
        else:
            content = f'[{message_type}]'
        
        # Nome do contato
        push_name = message_data.get('pushName', '')
        
        # Log da mensagem recebida
        direction_str = "📤 ENVIADA" if from_me else "📥 RECEBIDA"
        logger.info(f"{direction_str} [WEBHOOK] {phone}: {content[:50]}...")
        logger.info(f"   Tenant: {tenant.name} | Message ID: {message_id}")
        
        # Busca ou cria conversa
        # Nova conversa vai para INBOX (pending) sem departamento
        conversation, created = Conversation.objects.get_or_create(
            tenant=tenant,
            contact_phone=phone,
            defaults={
                'department': None,  # Inbox: sem departamento
                'contact_name': push_name,
                'status': 'pending'  # Pendente para classificação
            }
        )
        
        if created:
            logger.info(f"✅ [WEBHOOK] Nova conversa criada: {phone} (Inbox)")
        else:
            # Se conversa estava fechada, reabrir automaticamente
            if conversation.status == 'closed':
                conversation.status = 'pending' if not from_me else 'open'
                conversation.save(update_fields=['status'])
                status_str = "Inbox" if not from_me else "Aberta"
                logger.info(f"🔄 [WEBHOOK] Conversa {phone} reaberta automaticamente ({status_str})")
        
        # Atualiza nome se mudou
        if push_name and conversation.contact_name != push_name:
            conversation.contact_name = push_name
            conversation.save(update_fields=['contact_name'])
        
        # Cria mensagem
        direction = 'outgoing' if from_me else 'incoming'
        
        message, msg_created = Message.objects.get_or_create(
            message_id=message_id,
            defaults={
                'conversation': conversation,
                'content': content,
                'direction': direction,
                'status': 'sent',
                'evolution_status': 'sent'
            }
        )
        
        if msg_created:
            logger.info(f"✅ [WEBHOOK] Mensagem {direction} salva no banco")
            logger.info(f"   ID: {message.id} | Conversa: {conversation.id}")
            
            # Se tiver anexo, processa
            attachment_url = None
            mime_type = None
            filename = ''
            
            if message_type == 'imageMessage':
                attachment_url = message_info.get('imageMessage', {}).get('url')
                mime_type = message_info.get('imageMessage', {}).get('mimetype', 'image/jpeg')
                filename = f"{message.id}.jpg"
            elif message_type == 'videoMessage':
                attachment_url = message_info.get('videoMessage', {}).get('url')
                mime_type = message_info.get('videoMessage', {}).get('mimetype', 'video/mp4')
                filename = f"{message.id}.mp4"
            elif message_type == 'documentMessage':
                attachment_url = message_info.get('documentMessage', {}).get('url')
                mime_type = message_info.get('documentMessage', {}).get('mimetype', 'application/octet-stream')
                filename = message_info.get('documentMessage', {}).get('fileName', f"{message.id}.bin")
            elif message_type == 'audioMessage':
                attachment_url = message_info.get('audioMessage', {}).get('url')
                mime_type = message_info.get('audioMessage', {}).get('mimetype', 'audio/ogg')
                filename = f"{message.id}.ogg"
            
            if attachment_url:
                attachment = MessageAttachment.objects.create(
                    message=message,
                    tenant=tenant,
                    original_filename=filename,
                    mime_type=mime_type,
                    file_path='',  # Será preenchido após download
                    file_url=attachment_url,
                    storage_type='local'
                )
                
                # Enfileira download
                download_attachment.delay(str(attachment.id), attachment_url)
                logger.info(f"📎 [WEBHOOK] Anexo enfileirado para download: {filename}")
            
            # Broadcast via WebSocket
            logger.info(f"📡 [WEBHOOK] Enviando para WebSocket...")
            broadcast_message_to_websocket(message, conversation)
        
        else:
            logger.info(f"ℹ️ [WEBHOOK] Mensagem já existe no banco: {message_id}")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.upsert: {e}", exc_info=True)


def handle_message_update(data, tenant):
    """
    Processa evento de atualização de status (messages.update).
    Atualiza status: delivered, read
    """
    logger.info(f"🔄 [WEBHOOK UPDATE] Iniciando processamento...")
    
    try:
        message_data = data.get('data', {})
        
        # Estrutura pode variar: key.id ou messageId direto
        key = message_data.get('key', {})
        message_id = key.get('id') or message_data.get('messageId')
        
        # Status: delivered, read
        update = message_data.get('update', {})
        status_value = update.get('status') or message_data.get('status', '').upper()
        
        logger.info(f"🔍 [WEBHOOK UPDATE] Buscando mensagem: {message_id}")
        logger.info(f"   Status recebido: {status_value}")
        
        if not message_id or not status_value:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Dados insuficientes!")
            logger.warning(f"   message_id: {message_id}")
            logger.warning(f"   status: {status_value}")
            return
        
        # Busca mensagem
        try:
            message = Message.objects.select_related('conversation').get(message_id=message_id)
            logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada!")
            logger.info(f"   Conversa: {message.conversation.contact_phone}")
            logger.info(f"   Status atual: {message.status}")
        except Message.DoesNotExist:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Mensagem não encontrada no banco: {message_id}")
            return
        
        # Mapeia status (aceita múltiplos formatos)
        status_map = {
            'PENDING': 'pending',
            'SERVER_ACK': 'sent',
            'DELIVERY_ACK': 'delivered',
            'READ': 'seen',
            # Formatos alternativos
            'delivered': 'delivered',
            'delivery_ack': 'delivered',
            'read': 'seen',
            'read_ack': 'seen',
            'sent': 'sent'
        }
        
        new_status = status_map.get(status_value.lower()) or status_map.get(status_value)
        
        if not new_status:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Status não mapeado: {status_value}")
            return
        
        if message.status != new_status:
            old_status = message.status
            message.status = new_status
            message.evolution_status = status_value
            message.save(update_fields=['status', 'evolution_status'])
            
            logger.info(f"✅ [WEBHOOK UPDATE] Status atualizado!")
            logger.info(f"   {old_status} → {new_status}")
            logger.info(f"   Evolution status: {status_value}")
            
            # Broadcast via WebSocket
            logger.info(f"📡 [WEBHOOK UPDATE] Enviando atualização via WebSocket...")
            broadcast_status_update(message)
        else:
            logger.info(f"ℹ️ [WEBHOOK UPDATE] Status já está como '{new_status}', sem alteração")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.update: {e}", exc_info=True)


def broadcast_message_to_websocket(message, conversation):
    """Envia nova mensagem via WebSocket para o grupo da conversa."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        
        from apps.chat.api.serializers import MessageSerializer
        message_data = MessageSerializer(message).data
        
        logger.info(f"📡 [WEBSOCKET] Preparando broadcast...")
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Direction: {message.direction}")
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data
            }
        )
        
        logger.info(f"✅ [WEBSOCKET] Mensagem broadcast com sucesso!")
        logger.info(f"   Message ID: {message.id} | Content: {message.content[:30]}...")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast: {e}", exc_info=True)


def broadcast_status_update(message):
    """Envia atualização de status via WebSocket."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
        
        logger.info(f"📡 [WEBSOCKET STATUS] Preparando broadcast...")
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Novo status: {message.status}")
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_status_update',
                'message_id': str(message.id),
                'status': message.status
            }
        )
        
        logger.info(f"✅ [WEBSOCKET STATUS] Atualização broadcast com sucesso!")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET STATUS] Erro ao fazer broadcast: {e}", exc_info=True)

