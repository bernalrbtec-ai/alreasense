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
from apps.campaigns.models import CampaignContact, CampaignNotification
# CampaignNotification reativado
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
    
    # IP detection logs removed for cleaner output
    
    return ip

# 🚫 FUNÇÃO DE VALIDAÇÃO DE ORIGEM REMOVIDA COMPLETAMENTE


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_http_methods(["POST", "GET"]), name='dispatch')
class EvolutionWebhookView(APIView):
    permission_classes = [AllowAny]  # Não requer autenticação
    """Webhook para receber eventos do Evolution API."""
    
    def post(self, request):
        try:
            # Log básico do webhook
            # Webhook received - log removed for cleaner output
            
            # Parse JSON data
            data = json.loads(request.body)
            
            # Generate unique event ID
            event_id = generate_event_id(data)
            # Webhook received - log removed for cleaner output
            
            # Log completo do JSON para debug
            # Full webhook data logging removed for cleaner output
            
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
            # GET webhook debug logs removed for cleaner output
            
            # 🚫 VALIDAÇÃO DE ORIGEM REMOVIDA COMPLETAMENTE
            # GET Webhook allowed - log removed for cleaner output
            
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
            
            # Extract contact data - data can be a string or dict!
            contact_data_raw = data.get('data', {})
            instance = data.get('instance', '')
            
            # Handle case where data is a string (JSON)
            if isinstance(contact_data_raw, str):
                try:
                    contact_data_raw = json.loads(contact_data_raw)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse contact data as JSON: {contact_data_raw}")
                    return JsonResponse({'status': 'error', 'message': 'Invalid JSON in data field'}, status=400)
            
            # Handle case where data is a single contact object
            if isinstance(contact_data_raw, dict):
                contacts_list = [contact_data_raw]
            elif isinstance(contact_data_raw, list):
                contacts_list = contact_data_raw
            else:
                logger.error(f"Unexpected data type for contacts: {type(contact_data_raw)}")
                return JsonResponse({'status': 'error', 'message': 'Invalid data format'}, status=400)
            
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
                
                # Criar notificação se mensagem for de contato (não do bot)
                if not from_me and text_content.strip():
                    self.create_campaign_notification(
                        message_obj, sender, text_content, tenant, connection
                    )
                
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
            
            # Extract message info from Evolution API structure
            chat_id = update_data.get('remoteJid', '')
            message_id = update_data.get('messageId', '')  # Evolution API field
            status = update_data.get('status', '').lower()  # Convert to lowercase
            key_id = update_data.get('keyId', '')
            
            logger.info(f"Message update: messageId={message_id}, keyId={key_id}, status={status}, chat_id={chat_id}")
            
            # Find message in database by chat_id and text content
            # Since we don't have message_id field, we'll need to match differently
            try:
                logger.info(f"Processing message update for chat_id: {chat_id}, status: {status}")
                
                # Try both messageId and keyId for matching
                success = False
                if message_id:
                    success = self.update_campaign_contact_by_message_id(message_id, status)
                    if success:
                        self.update_message_model_by_message_id(message_id, status)
                
                if not success and key_id:
                    logger.info(f"Trying with keyId instead: {key_id}")
                    success = self.update_campaign_contact_by_message_id(key_id, status)
                    if success:
                        self.update_message_model_by_message_id(key_id, status)
                
            except Exception as e:
                logger.error(f"Error updating message status: {str(e)}")
            
            return Response({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error handling message update: {str(e)}")
            return JsonResponse({'error': 'Message update failed'}, status=500)
    
    def update_campaign_contact_by_message_id(self, message_id, status):
        """Update campaign contact status by WhatsApp message ID."""
        try:
            from apps.campaigns.models import CampaignContact
            
            # Debug search logs removed for cleaner output
            
            # Find campaign contact by WhatsApp message ID
            campaign_contact = CampaignContact.objects.filter(
                whatsapp_message_id=message_id
            ).first()
            
            if campaign_contact:
                logger.info(f"✅ Found CampaignContact: {campaign_contact.id} for message_id: {message_id}")
                # Update status based on Evolution API status
                if status in ['delivered', 'delivery_ack']:
                    campaign_contact.delivered_at = timezone.now()
                    campaign_contact.status = 'delivered'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as delivered (status: {status})")
                    
                elif status in ['read', 'read_ack']:
                    # Se ainda não foi entregue, marcar como entregue primeiro
                    if not campaign_contact.delivered_at:
                        campaign_contact.delivered_at = timezone.now()
                    campaign_contact.read_at = timezone.now()
                    campaign_contact.status = 'read'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as read (status: {status})")
                    
                elif status in ['failed', 'error']:
                    campaign_contact.failed_at = timezone.now()
                    campaign_contact.error_message = f"Message failed: {status}"
                    campaign_contact.status = 'failed'
                    logger.info(f"Campaign contact {campaign_contact.id} marked as failed (status: {status})")
                
                else:
                    logger.warning(f"Unknown status received: {status}")
                
                campaign_contact.save()
                
                # 📊 ATUALIZAR LOG COM INFORMAÇÕES DE ENTREGA/LEITURA
                self.update_campaign_log(campaign_contact, status)
                
                # Update campaign stats
                self.update_campaign_stats(campaign_contact.campaign)
                
                # Update delivery status in the log
                from apps.campaigns.models import CampaignLog
                # Webhook delivery status logs removed for cleaner output
                if status in ['delivered', 'delivery_ack']:
                    CampaignLog.update_message_delivery_status(campaign_contact, 'delivered')
                    logger.info(f"✅ [WEBHOOK] Log de entrega processado")
                elif status in ['read', 'read_ack']:
                    CampaignLog.update_message_delivery_status(campaign_contact, 'read')
                    logger.info(f"✅ [WEBHOOK] Log de leitura processado")
                
                return True
            else:
                logger.warning(f"❌ No CampaignContact found for message_id: {message_id}")
                # Debug: List all CampaignContacts with whatsapp_message_id
                all_contacts = CampaignContact.objects.filter(whatsapp_message_id__isnull=False)
                # Debug logs removed for cleaner output
                return False
                
        except Exception as e:
            logger.error(f"Error updating campaign contact by message_id: {str(e)}")
            return False
    
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
    
    def update_campaign_log(self, campaign_contact, status):
        """Atualizar log existente com informações de entrega/leitura"""
        try:
            from apps.campaigns.models import CampaignLog
            
            # Buscar log de envio para este contato
            log = CampaignLog.objects.filter(
                campaign=campaign_contact.campaign,
                campaign_contact=campaign_contact,
                log_type='message_sent'
            ).first()
            
            if log:
                # Atualizar details com informações de entrega/leitura
                if not log.details:
                    log.details = {}
                
                if status in ['delivered', 'delivery_ack']:
                    log.details['delivered_at'] = timezone.now().isoformat()
                    logger.info(f"📬 Log atualizado: Mensagem entregue para {campaign_contact.contact.name}")
                    
                elif status in ['read', 'read_ack']:
                    # Se ainda não tem delivered_at, adicionar
                    if 'delivered_at' not in log.details:
                        log.details['delivered_at'] = timezone.now().isoformat()
                    log.details['read_at'] = timezone.now().isoformat()
                    logger.info(f"👁️ Log atualizado: Mensagem lida por {campaign_contact.contact.name}")
                
                log.save()
            else:
                logger.warning(f"⚠️ Log de envio não encontrado para contato {campaign_contact.id}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar log: {str(e)}")
    
    def update_campaign_stats(self, campaign):
        """Update campaign statistics."""
        try:
            from apps.campaigns.models import CampaignContact
            from django.db import models
            
            total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
            sent_count = CampaignContact.objects.filter(campaign=campaign, status__in=['sent', 'delivered', 'read']).count()
            # Contar como entregues: mensagens com status 'delivered' OU que foram lidas (têm read_at)
            from django.db.models import Q
            delivered_count = CampaignContact.objects.filter(
                campaign=campaign
            ).filter(
                Q(status='delivered') | Q(read_at__isnull=False)
            ).count()
            read_count = CampaignContact.objects.filter(campaign=campaign, status='read').count()
            failed_count = CampaignContact.objects.filter(campaign=campaign, status='failed').count()
            
            # Atualizar campos da campanha
            campaign.messages_sent = sent_count
            campaign.messages_delivered = delivered_count
            campaign.messages_read = read_count
            campaign.messages_failed = failed_count
            campaign.save(update_fields=['messages_sent', 'messages_delivered', 'messages_read', 'messages_failed'])
            
            logger.info(f"✅ Campaign {campaign.id} stats updated: {sent_count} sent, {delivered_count} delivered, {read_count} read, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error updating campaign stats: {str(e)}")
    
    def update_message_model_by_message_id(self, message_id, status):
        """Update Message model status by WhatsApp message ID."""
        try:
            # Find campaign contact first to get the message details
            from apps.campaigns.models import CampaignContact
            
            campaign_contact = CampaignContact.objects.filter(
                whatsapp_message_id=message_id
            ).first()
            
            if campaign_contact:
                # Find corresponding Message record
                chat_id = f"campaign_{campaign_contact.campaign.id}_{campaign_contact.contact.id}"
                sender = f"campaign_{campaign_contact.campaign.id}"
                
                message_obj = Message.objects.filter(
                    chat_id=chat_id,
                    sender=sender,
                    tenant=campaign_contact.campaign.tenant
                ).first()
                
                if message_obj:
                    # Update Message model with delivery status
                    if status == 'delivered':
                        # Add delivery timestamp (we can use a custom field or update existing)
                        logger.info(f"Message {message_obj.id} marked as delivered in Message model")
                        # Note: Message model doesn't have delivery fields, but we can track in summary
                        if not message_obj.summary:
                            message_obj.summary = f"Status: delivered at {timezone.now().isoformat()}"
                        else:
                            message_obj.summary += f" | delivered at {timezone.now().isoformat()}"
                        message_obj.save(update_fields=['summary'])
                        
                    elif status == 'read':
                        logger.info(f"Message {message_obj.id} marked as read in Message model")
                        if not message_obj.summary:
                            message_obj.summary = f"Status: read at {timezone.now().isoformat()}"
                        else:
                            message_obj.summary += f" | read at {timezone.now().isoformat()}"
                        message_obj.save(update_fields=['summary'])
                        
                    elif status == 'failed':
                        logger.info(f"Message {message_obj.id} marked as failed in Message model")
                        if not message_obj.summary:
                            message_obj.summary = f"Status: failed at {timezone.now().isoformat()}"
                        else:
                            message_obj.summary += f" | failed at {timezone.now().isoformat()}"
                        message_obj.save(update_fields=['summary'])
                    
                    return True
                else:
                    logger.info(f"No Message record found for campaign message {message_id}")
                    return False
            else:
                logger.info(f"No CampaignContact found for message_id: {message_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating Message model by message_id: {str(e)}")
            return False

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
    
    def create_campaign_notification(self, message_obj, sender_phone, message_content, tenant, connection):
        """Criar notificação de campanha quando contato responde"""
        try:
            # Extrair número do telefone (remover @s.whatsapp.net)
            phone_number = sender_phone.split('@')[0] if '@' in sender_phone else sender_phone
            
            # Buscar contato pelo telefone
            from apps.contacts.models import Contact
            contact = Contact.objects.filter(
                tenant=tenant,
                phone=phone_number,
                is_active=True
            ).first()
            
            if not contact:
                logger.info(f"Contato não encontrado para telefone: {phone_number}")
                return
            
            # Buscar campanha ativa onde este contato foi enviado
            campaign_contact = CampaignContact.objects.filter(
                contact=contact,
                campaign__tenant=tenant,
                campaign__status__in=['running', 'completed', 'paused']
            ).order_by('-campaign__created_at').first()
            
            if not campaign_contact:
                logger.info(f"Nenhuma campanha encontrada para contato: {contact.name}")
                return
            
            # Buscar instância WhatsApp
            from apps.notifications.models import WhatsAppInstance
            instance = WhatsAppInstance.objects.filter(
                tenant=tenant,
                phone_number=phone_number
            ).first()
            
            if not instance:
                logger.info(f"Instância WhatsApp não encontrada para telefone: {phone_number}")
                return
            
            # Criar notificação
            notification = CampaignNotification.objects.create(
                tenant=tenant,
                campaign=campaign_contact.campaign,
                contact=contact,
                campaign_contact=campaign_contact,
                instance=instance,
                notification_type='response',
                status='unread',
                received_message=message_content,
                whatsapp_message_id=message_obj.message_id,
                details={
                    'message_type': 'text',
                    'chat_id': message_obj.chat_id,
                    'connection_id': str(connection.id),
                }
            )
            
            # Log da notificação criada
            from apps.campaigns.models import CampaignLog
            CampaignLog.log_notification_created(
                campaign=campaign_contact.campaign,
                contact=contact,
                notification=notification,
                message_content=message_content
            )
            
            logger.info(f"✅ Notificação criada: {notification.id} para {contact.name} na campanha {campaign_contact.campaign.name}")
            
        except Exception as e:
            logger.error(f"Erro ao criar notificação de campanha: {str(e)}")
            import traceback
            traceback.print_exc()
