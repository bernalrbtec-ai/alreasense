import json
import logging
import socket
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from datetime import datetime
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import EvolutionConnection
from apps.chat_messages.models import Message
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.campaigns.models import CampaignContact
import uuid

logger = logging.getLogger(__name__)

# Configuração de desenvolvimento (permitir todos em dev)
import os
ALLOW_ALL_ORIGINS_IN_DEV = os.getenv('ALLOW_ALL_WEBHOOK_ORIGINS', 'False').lower() == 'true'

# Lista de IPs/DNS permitidos para webhook (via variáveis de ambiente)
def get_allowed_webhook_origins():
    """Get allowed webhook origins from environment variables."""
    origins_str = os.getenv('ALLOWED_WEBHOOK_ORIGINS', 'evo.rbtec.com.br')
    # Suporta múltiplos IPs/DNS separados por vírgula
    origins = [origin.strip() for origin in origins_str.split(',') if origin.strip()]
    return origins

ALLOWED_WEBHOOK_ORIGINS = get_allowed_webhook_origins()

# Log das configurações carregadas
logger.info(f"🔒 Webhook security config: ALLOW_ALL_ORIGINS_IN_DEV={ALLOW_ALL_ORIGINS_IN_DEV}")
logger.info(f"🔒 Allowed webhook origins: {ALLOWED_WEBHOOK_ORIGINS}")

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_allowed_origin(request):
    """Check if request origin is allowed for webhook."""
    client_ip = get_client_ip(request)
    
    # Em desenvolvimento, permitir todos os IPs se configurado
    if ALLOW_ALL_ORIGINS_IN_DEV:
        return True, f"Development mode: allowing {client_ip}"
    
    # Verificar se o IP está na lista de permitidos
    for allowed_origin in ALLOWED_WEBHOOK_ORIGINS:
        try:
            # Se for um DNS, resolver para IP
            if not allowed_origin.replace('.', '').isdigit():
                resolved_ips = socket.gethostbyname_ex(allowed_origin)[2]
                if client_ip in resolved_ips:
                    return True, f"DNS {allowed_origin} resolved to {client_ip}"
            # Se for um IP direto
            elif client_ip == allowed_origin:
                return True, f"Direct IP match: {client_ip}"
        except socket.gaierror:
            logger.warning(f"Could not resolve DNS: {allowed_origin}")
            continue
    
    return False, f"IP {client_ip} not in allowed origins: {ALLOWED_WEBHOOK_ORIGINS}"


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["POST"]), name='dispatch')
class EvolutionWebhookView(APIView):
    permission_classes = [AllowAny]  # Não requer autenticação
    """Webhook para receber eventos do Evolution API."""
    
    def post(self, request):
        try:
            # 🔒 VALIDAÇÃO DE SEGURANÇA: Verificar origem
            is_allowed, reason = is_allowed_origin(request)
            if not is_allowed:
                logger.warning(f"🚫 Webhook blocked: {reason}")
                return Response({'error': 'Unauthorized origin'}, status=403)
            
            logger.info(f"✅ Webhook allowed: {reason}")
            
            # Parse JSON data
            data = json.loads(request.body)
            logger.info(f"Webhook received: {json.dumps(data, indent=2)}")
            
            # Process different event types
            event_type = data.get('event')
            
            if event_type == 'messages.upsert':
                return self.handle_message_upsert(data)
            elif event_type == 'messages.update':
                return self.handle_message_update(data)
            elif event_type == 'connection.update':
                return self.handle_connection_update(data)
            elif event_type == 'presence.update':
                return self.handle_presence_update(data)
            else:
                logger.info(f"Unhandled event type: {event_type}")
                return JsonResponse({'status': 'ignored', 'event': event_type})
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def handle_message_upsert(self, data):
        """Handle new messages from Evolution API."""
        try:
            messages = data.get('data', {}).get('messages', [])
            instance = data.get('data', {}).get('instance', 'default')
            
            for msg_data in messages:
                self.process_message(msg_data, instance)
            
            return JsonResponse({'status': 'success', 'processed': len(messages)})
            
        except Exception as e:
            logger.error(f"Error processing messages: {str(e)}")
            return JsonResponse({'error': 'Message processing failed'}, status=500)
    
    def process_message(self, msg_data, instance):
        """Process individual message."""
        try:
            # Extract message data
            key = msg_data.get('key', {})
            message = msg_data.get('message', {})
            
            # Get basic info
            chat_id = key.get('remoteJid', '')
            message_id = key.get('id', '')
            from_me = key.get('fromMe', False)
            
            # Get message content
            message_type = message.get('messageType', 'text')
            timestamp = msg_data.get('messageTimestamp', int(timezone.now().timestamp()))
            
            # Extract text content
            text_content = ''
            if message_type == 'conversation':
                text_content = message.get('conversation', '')
            elif message_type == 'extendedTextMessage':
                text_content = message.get('extendedTextMessage', {}).get('text', '')
            elif message_type == 'imageMessage':
                text_content = message.get('imageMessage', {}).get('caption', '')
            elif message_type == 'videoMessage':
                text_content = message.get('videoMessage', {}).get('caption', '')
            elif message_type == 'documentMessage':
                text_content = message.get('documentMessage', {}).get('caption', '')
            
            # Determine sender
            if from_me:
                sender = 'bot'  # Messages sent by us
            else:
                sender = chat_id.split('@')[0]  # Messages from customer
            
            # Get or create tenant (for now, use default)
            tenant = Tenant.objects.first()
            if not tenant:
                tenant = Tenant.objects.create(
                    name='Default Tenant',
                    plan='starter',
                    status='active'
                )
            
            # Get or create Evolution connection
            connection, created = EvolutionConnection.objects.get_or_create(
                name=f'Evolution {instance}',
                defaults={
                    'base_url': 'https://evo.rbtec.com.br',
                    'api_key': '584B4A4A-0815-AC86-DC39-C38FC27E8E17',
                    'webhook_url': f'https://alreasense-production.up.railway.app/api/webhooks/evolution/',
                    'is_active': True,
                    'status': 'active'
                }
            )
            
            # Create message record
            message_obj, created = Message.objects.get_or_create(
                chat_id=chat_id,
                message_id=message_id,
                defaults={
                    'tenant': tenant,
                    'connection': connection,
                    'sender': sender,
                    'text': text_content,
                    'created_at': datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    'sentiment': None,  # Will be filled by AI processing
                    'emotion': None,
                    'satisfaction': None,
                    'tone': None,
                    'summary': None,
                }
            )
            
            if created:
                logger.info(f"New message created: {message_obj.id} from {sender}")
                
                # TODO: Trigger AI analysis
                # self.trigger_ai_analysis(message_obj)
                
            else:
                logger.info(f"Message already exists: {message_obj.id}")
            
        except Exception as e:
            logger.error(f"Error processing individual message: {str(e)}")
    
    def handle_message_update(self, data):
        """Handle message status updates (delivered, read, etc.)."""
        try:
            update_data = data.get('data', {})
            key = update_data.get('key', {})
            update = update_data.get('update', {})
            
            # Extract message info
            chat_id = key.get('remoteJid', '')
            message_id = key.get('id', '')
            status = update.get('status', '')
            timestamp = update.get('timestamp')
            
            logger.info(f"Message update: {message_id} status={status}")
            
            # Find message in database
            try:
                message_obj = Message.objects.get(
                    chat_id=chat_id,
                    message_id=message_id
                )
                
                # Update message status based on Evolution API status
                if status == 'delivered':
                    message_obj.delivered_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    logger.info(f"Message {message_id} marked as delivered")
                    
                elif status == 'read':
                    message_obj.read_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    logger.info(f"Message {message_id} marked as read")
                    
                elif status == 'failed':
                    message_obj.failed_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    logger.info(f"Message {message_id} marked as failed")
                
                message_obj.save()
                
                # TODO: Update campaign contact status if this is a campaign message
                self.update_campaign_contact_status(message_obj, status, timestamp)
                
            except Message.DoesNotExist:
                logger.warning(f"Message not found: {message_id}")
            
            return Response({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error handling message update: {str(e)}")
            return JsonResponse({'error': 'Message update failed'}, status=500)
    
    def handle_connection_update(self, data):
        """Handle connection status updates."""
        try:
            # TODO: Update connection status
            logger.info(f"Connection update received: {data}")
            return Response({'status': 'success'})
        except Exception as e:
            logger.error(f"Error handling connection update: {str(e)}")
            return JsonResponse({'error': 'Connection update failed'}, status=500)
    
    def handle_presence_update(self, data):
        """Handle presence updates (online/offline)."""
        try:
            # TODO: Update presence status
            logger.info(f"Presence update received: {data}")
            return Response({'status': 'success'})
        except Exception as e:
            logger.error(f"Error handling presence update: {str(e)}")
            return JsonResponse({'error': 'Presence update failed'}, status=500)
