import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from datetime import datetime
from .models import EvolutionConnection
from apps.chat_messages.models import Message
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
import uuid

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["POST"]), name='dispatch')
class EvolutionWebhookView(View):
    """Webhook para receber eventos do Evolution API."""
    
    def post(self, request):
        try:
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
            # TODO: Update message status
            logger.info(f"Message update received: {data}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error handling message update: {str(e)}")
            return JsonResponse({'error': 'Message update failed'}, status=500)
    
    def handle_connection_update(self, data):
        """Handle connection status updates."""
        try:
            # TODO: Update connection status
            logger.info(f"Connection update received: {data}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error handling connection update: {str(e)}")
            return JsonResponse({'error': 'Connection update failed'}, status=500)
    
    def handle_presence_update(self, data):
        """Handle presence updates (online/offline)."""
        try:
            # TODO: Update presence status
            logger.info(f"Presence update received: {data}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error handling presence update: {str(e)}")
            return JsonResponse({'error': 'Presence update failed'}, status=500)
