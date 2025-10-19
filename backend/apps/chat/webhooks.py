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
        
        # Busca ou cria conversa
        # Assume departamento padrão (primeiro do tenant)
        default_dept = tenant.departments.first()
        
        if not default_dept:
            logger.error(f"❌ [WEBHOOK] Tenant {tenant.name} não tem departamentos")
            return
        
        conversation, created = Conversation.objects.get_or_create(
            tenant=tenant,
            contact_phone=phone,
            defaults={
                'department': default_dept,
                'contact_name': push_name,
                'status': 'open'
            }
        )
        
        if created:
            logger.info(f"✅ [WEBHOOK] Nova conversa criada: {phone}")
        else:
            # Se conversa estava fechada, reabrir automaticamente
            if conversation.status == 'closed':
                conversation.status = 'open'
                conversation.save(update_fields=['status'])
                logger.info(f"🔄 [WEBHOOK] Conversa {phone} reaberta automaticamente")
        
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
            logger.info(f"✅ [WEBHOOK] Nova mensagem criada: {message_id}")
            
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
            broadcast_message_to_websocket(message, conversation)
        
        else:
            logger.info(f"ℹ️ [WEBHOOK] Mensagem já existe: {message_id}")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.upsert: {e}", exc_info=True)


def handle_message_update(data, tenant):
    """
    Processa evento de atualização de status (messages.update).
    Atualiza status: delivered, read
    """
    try:
        message_data = data.get('data', {})
        
        # Estrutura pode variar: key.id ou messageId direto
        key = message_data.get('key', {})
        message_id = key.get('id') or message_data.get('messageId')
        
        # Status: delivered, read
        update = message_data.get('update', {})
        status_value = update.get('status') or message_data.get('status', '').upper()
        
        if not message_id or not status_value:
            logger.warning(f"⚠️ [WEBHOOK] Dados insuficientes: message_id={message_id}, status={status_value}")
            return
        
        # Busca mensagem
        try:
            message = Message.objects.get(message_id=message_id)
        except Message.DoesNotExist:
            logger.warning(f"⚠️ [WEBHOOK] Mensagem não encontrada: {message_id}")
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
        
        if new_status and message.status != new_status:
            message.status = new_status
            message.evolution_status = status_value
            message.save(update_fields=['status', 'evolution_status'])
            
            logger.info(f"✅ [WEBHOOK] Status atualizado: {message_id} -> {new_status} (raw: {status_value})")
            
            # Broadcast via WebSocket
            broadcast_status_update(message)
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.update: {e}", exc_info=True)


def broadcast_message_to_websocket(message, conversation):
    """Envia nova mensagem via WebSocket para o grupo da conversa."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        
        from apps.chat.api.serializers import MessageSerializer
        message_data = MessageSerializer(message).data
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data
            }
        )
        
        logger.info(f"📡 [WEBSOCKET] Mensagem broadcast: {message.id}")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast: {e}", exc_info=True)


def broadcast_status_update(message):
    """Envia atualização de status via WebSocket."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{message.conversation.tenant_id}_conversation_{message.conversation_id}"
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_status_update',
                'message_id': str(message.id),
                'status': message.status
            }
        )
        
        logger.info(f"📡 [WEBSOCKET] Status broadcast: {message.id} -> {message.status}")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast de status: {e}", exc_info=True)

