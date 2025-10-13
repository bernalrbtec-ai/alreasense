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
from .webhook_cache import WebhookCache, generate_event_id
from apps.chat_messages.models import Message
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.campaigns.models import CampaignContact
import uuid

logger = logging.getLogger(__name__)

# 🚫 CONFIGURAÇÃO DE VALIDAÇÃO REMOVIDA COMPLETAMENTE

def get_client_ip(request):
    """Get client IP address from request."""
    # Tentar múltiplas fontes de IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    # Log detalhado do IP
    logger.info(f"🔍 IP Detection - REMOTE_ADDR: {request.META.get('REMOTE_ADDR')}")
    logger.info(f"🔍 IP Detection - X_FORWARDED_FOR: {x_forwarded_for}")
    logger.info(f"🔍 IP Detection - Final IP: {ip}")
    
    return ip

# 🚫 FUNÇÃO DE VALIDAÇÃO DE ORIGEM REMOVIDA COMPLETAMENTE


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["POST", "GET"]), name='dispatch')
class EvolutionWebhookView(APIView):
    permission_classes = [AllowAny]  # Não requer autenticação
    """Webhook para receber eventos do Evolution API."""
    
    def post(self, request):
        try:
            # 🔍 LOG DETALHADO PARA DEBUG
            client_ip = get_client_ip(request)
            logger.info(f"🔍 POST Webhook - IP: {client_ip}, Path: {request.path}, Method: {request.method}")
            logger.info(f"🔍 Headers: {dict(request.headers)}")
            logger.info(f"🔍 META keys: {list(request.META.keys())}")
            logger.info(f"🔍 REMOTE_ADDR: {request.META.get('REMOTE_ADDR')}")
            logger.info(f"🔍 HTTP_X_FORWARDED_FOR: {request.META.get('HTTP_X_FORWARDED_FOR')}")
            logger.info(f"🔍 HTTP_HOST: {request.META.get('HTTP_HOST')}")
            logger.info(f"🔍 CONTENT_TYPE: {request.META.get('CONTENT_TYPE')}")
            
            # Log do body
            if request.body:
                try:
                    body_str = request.body.decode('utf-8')
                    logger.info(f"🔍 Body length: {len(body_str)}")
                    logger.info(f"🔍 Body preview: {body_str[:200]}...")
                except Exception as e:
                    logger.error(f"🔍 Error decoding body: {str(e)}")
            
            # 🚫 VALIDAÇÃO DE ORIGEM REMOVIDA COMPLETAMENTE
            logger.info(f"✅ Webhook allowed: NO VALIDATION - ALL ORIGINS ACCEPTED")
            
            # Parse JSON data
            data = json.loads(request.body)
            
            # Generate unique event ID
            event_id = generate_event_id(data)
            logger.info(f"📥 Webhook received: {event_id} - {data.get('event', 'unknown')}")
            
            # Log completo do JSON para debug
            logger.info(f"🔍 FULL WEBHOOK DATA: {json.dumps(data, indent=2)}")
            
            # Store event in Redis cache (24h)
            WebhookCache.store_event(event_id, data)
            logger.info(f"💾 Evento armazenado no cache: {event_id}")
            
            # Process different event types
            event_type = data.get('event')
            
            if event_type == 'messages.upsert':
                return self.handle_message_upsert(data)
            elif event_type == 'messages.update':
                return self.handle_message_update(data)
            elif event_type == 'messages.delete':
                return self.handle_message_delete(data)
            elif event_type == 'messages.edited':
                return self.handle_message_edited(data)
            elif event_type == 'connection.update':
                return self.handle_connection_update(data)
            elif event_type == 'presence.update':
                return self.handle_presence_update(data)
            elif event_type == 'contacts.update':
                return self.handle_contacts_update(data)
            elif event_type == 'contacts.upsert':
                return self.handle_contacts_upsert(data)
            elif event_type == 'contacts.set':
                return self.handle_contacts_set(data)
            elif event_type == 'chats.update':
                return self.handle_chats_update(data)
            elif event_type == 'chats.upsert':
                return self.handle_chats_upsert(data)
            elif event_type == 'chats.delete':
                return self.handle_chats_delete(data)
            elif event_type == 'chats.set':
                return self.handle_chats_set(data)
            elif event_type == 'groups.upsert':
                return self.handle_groups_upsert(data)
            elif event_type == 'groups.update':
                return self.handle_groups_update(data)
            elif event_type == 'group.participants.update':
                return self.handle_group_participants_update(data)
            elif event_type == 'send.message':
                return self.handle_send_message(data)
            else:
                logger.info(f"Unhandled event type: {event_type}")
                return JsonResponse({'status': 'ignored', 'event': event_type})
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def get(self, request):
        """Endpoint GET para evitar erro 403 no redirecionamento"""
        try:
            # 🔍 LOG DO IP PARA DEBUG
            client_ip = get_client_ip(request)
            logger.info(f"🔍 GET Webhook IP: {client_ip}")
            
            # 🚫 VALIDAÇÃO DE ORIGEM REMOVIDA COMPLETAMENTE
            logger.info(f"✅ GET Webhook allowed: NO VALIDATION - ALL ORIGINS ACCEPTED")
            
            return Response({
                'status': 'success',
                'message': 'Webhook endpoint is working',
                'timestamp': timezone.now().isoformat(),
                'ip': client_ip
            })
            
        except Exception as e:
            logger.error(f"GET Webhook error: {str(e)}")
            return Response({'error': 'Internal server error'}, status=500)
    
    def handle_contacts_update(self, data):
        """Handle contacts.update events from Evolution API."""
        try:
            logger.info(f"📞 Contacts update received: {json.dumps(data, indent=2)}")
            
            # Extract contact data - data is a LIST, not a dict!
            contacts_list = data.get('data', [])
            instance = data.get('instance', '')
            
            # Process each contact in the list
            for contact_data in contacts_list:
                remote_jid = contact_data.get('remoteJid', '')
                push_name = contact_data.get('pushName', '')
                profile_pic = contact_data.get('profilePicUrl', '')
                
                logger.info(f"📞 Contact updated - Instance: {instance}, JID: {remote_jid}, Name: {push_name}")
            
            # TODO: Update contact information in database if needed
            # This could be used to sync contact names and profile pictures
            
            return JsonResponse({'status': 'success', 'event': 'contacts.update'})
            
        except Exception as e:
            logger.error(f"Error handling contacts update: {str(e)}")
            return JsonResponse({'error': 'Contacts update failed'}, status=500)
    
    def handle_message_delete(self, data):
        """Handle messages.delete events."""
        logger.info(f"🗑️ Message deleted: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'messages.delete'})
    
    def handle_message_edited(self, data):
        """Handle messages.edited events."""
        logger.info(f"✏️ Message edited: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'messages.edited'})
    
    def handle_contacts_upsert(self, data):
        """Handle contacts.upsert events."""
        logger.info(f"📞 Contact upsert: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'contacts.upsert'})
    
    def handle_contacts_set(self, data):
        """Handle contacts.set events."""
        logger.info(f"📞 Contact set: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'contacts.set'})
    
    def handle_chats_update(self, data):
        """Handle chats.update events."""
        logger.info(f"💬 Chat updated: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'chats.update'})
    
    def handle_chats_upsert(self, data):
        """Handle chats.upsert events."""
        logger.info(f"💬 Chat upsert: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'chats.upsert'})
    
    def handle_chats_delete(self, data):
        """Handle chats.delete events."""
        logger.info(f"💬 Chat deleted: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'chats.delete'})
    
    def handle_chats_set(self, data):
        """Handle chats.set events."""
        logger.info(f"💬 Chat set: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'chats.set'})
    
    def handle_groups_upsert(self, data):
        """Handle groups.upsert events."""
        logger.info(f"👥 Group upsert: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'groups.upsert'})
    
    def handle_groups_update(self, data):
        """Handle groups.update events."""
        logger.info(f"👥 Group updated: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'groups.update'})
    
    def handle_group_participants_update(self, data):
        """Handle group.participants.update events."""
        logger.info(f"👥 Group participants updated: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'group.participants.update'})
    
    def handle_send_message(self, data):
        """Handle send.message events."""
        logger.info(f"📤 Message sent: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'send.message'})
    
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
    
    def update_campaign_contact_status(self, message_obj, status, timestamp):
        """Update campaign contact status based on message status."""
        try:
            # Find campaign contact by WhatsApp message ID
            campaign_contact = CampaignContact.objects.filter(
                whatsapp_message_id=message_obj.message_id
            ).first()
            
            if campaign_contact:
                # Update status based on Evolution API status
                if status == 'delivered':
                    campaign_contact.delivered_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    campaign_contact.status = 'delivered'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as delivered")
                    
                elif status == 'read':
                    campaign_contact.read_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    campaign_contact.status = 'read'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as read")
                    
                elif status == 'failed':
                    campaign_contact.failed_at = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                    campaign_contact.error_message = f"Message failed: {status}"
                    campaign_contact.status = 'failed'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as failed")
                
                campaign_contact.save()
                
                # Update campaign stats
                self.update_campaign_stats(campaign_contact.campaign)
                
        except Exception as e:
            logger.error(f"Error updating campaign contact status: {str(e)}")
    
    def update_campaign_stats(self, campaign):
        """Update campaign statistics."""
        try:
            from apps.campaigns.models import CampaignContact
            
            total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
            delivered_count = CampaignContact.objects.filter(campaign=campaign, status='delivered').count()
            read_count = CampaignContact.objects.filter(campaign=campaign, status='read').count()
            failed_count = CampaignContact.objects.filter(campaign=campaign, status='failed').count()
            
            logger.info(f"Campaign {campaign.id} stats: {delivered_count}/{total_contacts} delivered, {read_count} read, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error updating campaign stats: {str(e)}")
    
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
