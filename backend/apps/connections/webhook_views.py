import json
import logging
import socket
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone

from apps.chat.utils.instance_state import set_instance_state
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
            
                # 📸 Atualizar foto de perfil nas conversas E no Contact
                if profile_pic and remote_jid:
                    try:
                        # Buscar instância WhatsApp pelo nome (pode ser UUID ou friendly_name)
                        from apps.notifications.models import WhatsAppInstance
                        from django.db.models import Q
                        
                        whatsapp_instance = WhatsAppInstance.objects.filter(
                            Q(instance_name=instance) | Q(friendly_name=instance),
                            is_active=True
                        ).first()
                        
                        if whatsapp_instance:
                            # Extrair telefone (remover @s.whatsapp.net)
                            phone = remote_jid.replace('@s.whatsapp.net', '')
                            if not phone.startswith('+'):
                                phone = f'+{phone}'
                            
                            # ✅ NOVO: Atualizar Contact primeiro (fonte única de verdade)
                            from apps.contacts.models import Contact
                            from apps.notifications.services import normalize_phone
                            
                            # Normalizar telefone para busca
                            normalized_phone = normalize_phone(phone) or phone
                            
                            # Buscar contato pelo telefone normalizado
                            contact = Contact.objects.filter(
                                tenant=whatsapp_instance.tenant,
                                phone=normalized_phone
                            ).first()
                            
                            # Se não encontrou com telefone normalizado, tentar com telefone original
                            if not contact:
                                contact = Contact.objects.filter(
                                    tenant=whatsapp_instance.tenant,
                                    phone=phone
                                ).first()
                            
                            # ✅ Atualizar Contact apenas se URL mudou
                            if contact:
                                if contact.profile_pic_url != profile_pic:
                                    old_contact_pic = contact.profile_pic_url
                                    contact.profile_pic_url = profile_pic
                                    contact.save(update_fields=['profile_pic_url'])
                                    logger.info(f"✅ [FOTO CONTACT] Atualizada foto do contato {contact.name} ({phone})")
                                    logger.info(f"   URL antiga: {old_contact_pic[:50] if old_contact_pic else 'N/A'}...")
                                    logger.info(f"   URL nova: {profile_pic[:50]}...")
                                else:
                                    logger.debug(f"🔄 [FOTO CONTACT] Foto do contato {contact.name} não mudou, mantendo atual")
                            else:
                                logger.debug(f"ℹ️ [FOTO CONTACT] Contato não encontrado para {phone}, apenas atualizando conversas")
                            
                            # Atualizar todas as conversas com esse telefone
                            from apps.chat.models import Conversation
                            
                            # Buscar conversas para verificar se URL mudou
                            conversations = Conversation.objects.filter(
                                tenant=whatsapp_instance.tenant,
                                contact_phone=phone
                            )
                            
                            old_profile_pics = {conv.id: conv.profile_pic_url for conv in conversations}
                            
                            updated_count = conversations.update(profile_pic_url=profile_pic)
                            
                            if updated_count > 0:
                                logger.info(f"✅ [FOTO CONVERSATION] Atualizada foto de perfil para {phone}: {profile_pic[:50]}...")
                                logger.info(f"   {updated_count} conversa(s) atualizada(s)")
                                
                                # Invalidar cache Redis se URL mudou
                                from django.core.cache import cache
                                import hashlib
                                
                                for conv_id, old_url in old_profile_pics.items():
                                    if old_url and old_url != profile_pic:
                                        # Invalidar cache da URL antiga
                                        old_cache_key = f"profile_pic:{hashlib.md5(old_url.encode()).hexdigest()}"
                                        cache.delete(old_cache_key)
                                        logger.info(f"🗑️ [CACHE] Invalidado cache da URL antiga: {old_cache_key}")
                                
                                # Broadcast atualização via WebSocket
                                try:
                                    from channels.layers import get_channel_layer
                                    from asgiref.sync import async_to_sync
                                    from apps.chat.api.serializers import ConversationSerializer
                                    
                                    channel_layer = get_channel_layer()
                                    
                                    # Buscar e enviar atualização de cada conversa
                                    conversations = Conversation.objects.filter(
                                        tenant=whatsapp_instance.tenant,
                                        contact_phone=phone
                                    )
                                    
                                    for conv in conversations:
                                        conv_data = ConversationSerializer(conv).data
                                        
                                        # Converter UUIDs
                                        def convert_uuids(obj):
                                            import uuid
                                            if isinstance(obj, uuid.UUID):
                                                return str(obj)
                                            elif isinstance(obj, dict):
                                                return {k: convert_uuids(v) for k, v in obj.items()}
                                            elif isinstance(obj, list):
                                                return [convert_uuids(item) for item in obj]
                                            return obj
                                        
                                        conv_data_clean = convert_uuids(conv_data)
                                        
                                        tenant_group = f"chat_tenant_{whatsapp_instance.tenant_id}"
                                        async_to_sync(channel_layer.group_send)(
                                            tenant_group,
                                            {
                                                'type': 'conversation_updated',
                                                'conversation': conv_data_clean
                                            }
                                        )
                                        logger.info(f"📡 [FOTO] Atualização broadcast para tenant via WebSocket")
                                except Exception as e:
                                    logger.error(f"❌ [FOTO] Erro ao broadcast: {e}")
                    except Exception as e:
                        logger.error(f"❌ [FOTO] Erro ao atualizar foto: {e}", exc_info=True)
            
            return JsonResponse({'status': 'success', 'event': 'contacts.update'})
            
        except Exception as e:
            logger.error(f"Error handling contacts update: {str(e)}")
            return JsonResponse({'error': 'Contacts update failed'}, status=500)
    
    def handle_message_delete(self, data):
        """Handle messages.delete events."""
        logger.info(f"🗑️ Message deleted: {data.get('event')}")
        
        # 💬 FLOW CHAT: Processar deleção de mensagem
        try:
            instance_name = data.get('instance')
            if instance_name:
                from apps.notifications.models import WhatsAppInstance
                from apps.connections.models import EvolutionConnection
                from django.db.models import Q
                
                # Buscar instância WhatsApp
                whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                    Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                    is_active=True
                ).first()
                
                # Buscar conexão Evolution
                connection = EvolutionConnection.objects.filter(is_active=True).first()
                
                if whatsapp_instance:
                    # ✅ CORREÇÃO: Chamar handler correto do chat/webhooks.py
                    from apps.chat.webhooks import handle_message_delete
                    handle_message_delete(
                        data,
                        tenant=whatsapp_instance.tenant,
                        connection=connection,
                        wa_instance=whatsapp_instance
                    )
                    logger.info(f"🗑️ [FLOW CHAT] Mensagem deletada processada para tenant {whatsapp_instance.tenant.name}")
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para: {instance_name}")
        except Exception as e:
            logger.error(f"❌ [FLOW CHAT] Erro ao processar messages.delete: {e}", exc_info=True)
        
        return JsonResponse({'status': 'success', 'event': 'messages.delete'})
    
    def handle_message_edited(self, data):
        """Handle messages.edited events."""
        logger.info(f"✏️ Message edited: {data.get('event')}")
        
        # 💬 FLOW CHAT: Processar edição de mensagem
        try:
            instance_name = data.get('instance')
            if instance_name:
                from apps.notifications.models import WhatsAppInstance
                from apps.connections.models import EvolutionConnection
                from django.db.models import Q
                
                whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                    Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                    is_active=True
                ).first()
                
                # Buscar conexão Evolution
                connection = EvolutionConnection.objects.filter(is_active=True).first()
                
                if whatsapp_instance:
                    logger.info(f"✏️ [FLOW CHAT] Mensagem editada para tenant {whatsapp_instance.tenant.name}")
                    # ✅ CORREÇÃO: Chamar handler correto do chat/webhooks.py
                    from apps.chat.webhooks import handle_message_edited
                    handle_message_edited(
                        data,
                        tenant=whatsapp_instance.tenant
                    )
                elif connection:
                    logger.info(f"✏️ [FLOW CHAT] Mensagem editada para tenant {connection.tenant.name}")
                    from apps.chat.webhooks import handle_message_edited
                    handle_message_edited(
                        data,
                        tenant=connection.tenant
                    )
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para: {instance_name}")
        except Exception as e:
            logger.error(f"❌ [FLOW CHAT] Erro ao processar messages.edited: {e}", exc_info=True)
        
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
        
        # 💬 FLOW CHAT: Processar atualização de chat para o módulo de chat
        try:
            instance_name = data.get('instance')
            if not instance_name:
                logger.warning("⚠️ [FLOW CHAT] chats.update sem instance_name")
                return JsonResponse({'status': 'success', 'event': 'chats.update'})
            
            from apps.chat.webhooks import handle_message_update as chat_handle_update
            from apps.notifications.models import WhatsAppInstance
            from django.db.models import Q
            
            # Buscar instância - Evolution API envia o "nome da instância" (ex: "RBTec")
            # Pode ser friendly_name OU instance_name (depende da configuração)
            whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                is_active=True
            ).first()
            
            if whatsapp_instance:
                chat_handle_update(data, whatsapp_instance.tenant)
                logger.info(f"💬 [FLOW CHAT] Chat atualizado para tenant {whatsapp_instance.tenant.name}")
            else:
                logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para: {instance_name}")
        except Exception as e:
            logger.error(f"❌ [FLOW CHAT] Erro ao processar chats.update: {e}", exc_info=True)
        
        return JsonResponse({'status': 'success', 'event': 'chats.update'})
    
    def handle_chats_upsert(self, data):
        """Handle chats.upsert events."""
        logger.info(f"💬 Chat upsert: {data.get('event')}")
        
        # 💬 FLOW CHAT: Processar novo chat
        try:
            instance_name = data.get('instance')
            if instance_name:
                from apps.notifications.models import WhatsAppInstance
                from django.db.models import Q
                
                whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                    Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                    is_active=True
                ).first()
                
                if whatsapp_instance:
                    logger.info(f"💬 [FLOW CHAT] Chat upsert para tenant {whatsapp_instance.tenant.name}")
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para: {instance_name}")
        except Exception as e:
            logger.error(f"❌ [FLOW CHAT] Erro ao processar chats.upsert: {e}", exc_info=True)
        
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
        
        # 💬 FLOW CHAT: Processar atualização de grupo
        try:
            instance_name = data.get('instance')
            if instance_name:
                from apps.notifications.models import WhatsAppInstance
                from django.db.models import Q
                
                whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                    Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                    is_active=True
                ).first()
                
                if whatsapp_instance:
                    logger.info(f"👥 [FLOW CHAT] Grupo atualizado para tenant {whatsapp_instance.tenant.name}")
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para: {instance_name}")
        except Exception as e:
            logger.error(f"❌ [FLOW CHAT] Erro ao processar groups.update: {e}", exc_info=True)
        
        return JsonResponse({'status': 'success', 'event': 'groups.update'})
    
    def handle_group_participants_update(self, data):
        """
        Handle group.participants.update events.
        
        Processa quando participantes são adicionados ou removidos de um grupo.
        Atualiza a lista de participantes na conversa e envia broadcast via WebSocket.
        """
        logger.info(f"👥 [GROUP PARTICIPANTS] Evento recebido: {data.get('event')}")
        logger.info(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
        
        try:
            instance_name = data.get('instance')
            group_jid = data.get('groupJid') or data.get('group_jid') or data.get('jid')
            
            if not instance_name or not group_jid:
                logger.warning(f"⚠️ [GROUP PARTICIPANTS] Dados incompletos: instance={instance_name}, groupJid={group_jid}")
                return JsonResponse({'status': 'error', 'message': 'Missing instance or groupJid'}, status=400)
            
            logger.info(f"👥 [GROUP PARTICIPANTS] Processando: instance={instance_name}, groupJid={group_jid}")
            
            # Buscar WhatsAppInstance
            from apps.notifications.models import WhatsAppInstance
            from django.db.models import Q
            from apps.chat.models import Conversation
            from apps.chat.api.views import clean_participants_for_metadata
            from django.utils import timezone
            from django.db import transaction
            from apps.chat.utils.websocket import broadcast_conversation_updated
            
            whatsapp_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                is_active=True
            ).first()
            
            if not whatsapp_instance:
                logger.warning(f"⚠️ [GROUP PARTICIPANTS] WhatsAppInstance não encontrada: {instance_name}")
                return JsonResponse({'status': 'error', 'message': 'Instance not found'}, status=404)
            
            tenant = whatsapp_instance.tenant
            logger.info(f"✅ [GROUP PARTICIPANTS] Tenant encontrado: {tenant.name}")
            
            # Buscar conversa do grupo
            # Normalizar group_jid para formato usado no banco
            normalized_group_jid = group_jid
            if not normalized_group_jid.endswith('@g.us'):
                if normalized_group_jid.endswith('@s.whatsapp.net'):
                    normalized_group_jid = normalized_group_jid.replace('@s.whatsapp.net', '@g.us')
                else:
                    normalized_group_jid = f"{normalized_group_jid.rstrip('@')}@g.us"
            
            # ✅ Buscar conversa do grupo com fallback para LID/metadados
            conversation_queryset = Conversation.objects.filter(
                tenant=tenant,
                conversation_type='group'
            )
            conversation = conversation_queryset.filter(
                Q(contact_phone=normalized_group_jid) |
                Q(contact_phone=group_jid) |
                Q(group_metadata__group_id=group_jid) |
                Q(group_metadata__group_id=normalized_group_jid) |
                Q(group_metadata__group_id_lid=group_jid)
            ).first()
            
            if not conversation:
                logger.warning(f"⚠️ [GROUP PARTICIPANTS] Conversa não encontrada")
                logger.warning(f"   group_jid: {group_jid}")
                logger.warning(f"   normalized_group_jid: {normalized_group_jid}")
                return JsonResponse({'status': 'error', 'message': 'Conversation not found'}, status=404)
            
            logger.info(f"✅ [GROUP PARTICIPANTS] Conversa encontrada: {conversation.id} - {conversation.contact_name}")
            
            # Extrair participantes adicionados e removidos
            participants_added = data.get('participants', {}).get('add', []) or data.get('added', []) or []
            participants_removed = data.get('participants', {}).get('remove', []) or data.get('removed', []) or []
            
            # Também verificar formato alternativo
            if not participants_added and not participants_removed:
                participants_data = data.get('participants', [])
                if isinstance(participants_data, list):
                    # Se é lista, pode ser lista completa de participantes
                    participants_added = participants_data
                elif isinstance(participants_data, dict):
                    participants_added = participants_data.get('add', [])
                    participants_removed = participants_data.get('remove', [])
            
            logger.info(f"👥 [GROUP PARTICIPANTS] Adicionados: {len(participants_added)}, Removidos: {len(participants_removed)}")
            
            # Buscar lista atual de participantes do grupo via API Evolution
            # Isso garante que temos a lista completa e atualizada
            from apps.notifications.models import EvolutionConnection
            import httpx
            
            connection = EvolutionConnection.objects.filter(is_active=True).first()
            if not connection:
                logger.warning(f"⚠️ [GROUP PARTICIPANTS] EvolutionConnection não encontrada")
                return JsonResponse({'status': 'error', 'message': 'Evolution connection not found'}, status=404)
            
            base_url = (whatsapp_instance.api_url or connection.base_url).rstrip('/')
            api_key = whatsapp_instance.api_key or connection.api_key
            
            if not base_url or not api_key:
                logger.warning(f"⚠️ [GROUP PARTICIPANTS] API URL ou key não configurados")
                return JsonResponse({'status': 'error', 'message': 'API not configured'}, status=500)
            
            headers = {'apikey': api_key, 'Content-Type': 'application/json'}
            
            # Buscar lista completa de participantes da API
            def normalize_digits(value: str) -> str:
                return ''.join(ch for ch in (value or '') if ch.isdigit())
            
            def extract_participant_identifiers(participant):
                identifiers = []
                if isinstance(participant, dict):
                    for key in ['jid', 'id', 'phone', 'phoneNumber', 'phone_number', 'participant', 'participantAlt']:
                        val = participant.get(key)
                        if val:
                            identifiers.append(val)
                elif isinstance(participant, str):
                    identifiers.append(participant)
                return identifiers
            
            try:
                endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                with httpx.Client(timeout=15.0) as client:
                    response = client.get(
                        endpoint,
                        params={'groupJid': group_jid, 'getParticipants': 'true'},
                        headers=headers
                    )
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ [GROUP PARTICIPANTS] Erro ao buscar participantes: {response.status_code}")
                    return JsonResponse({'status': 'error', 'message': f'API error: {response.status_code}'}, status=500)
                
                group_data = response.json()
                participants_list = group_data.get('participants', [])
                
                logger.info(f"✅ [GROUP PARTICIPANTS] {len(participants_list)} participantes obtidos da API")
                
                # Limpar participantes (remover LIDs)
                cleaned_participants = clean_participants_for_metadata(participants_list)
                
                # Verificar se participante corresponde à instância atual
                instance_digits = normalize_digits(whatsapp_instance.phone_number)
                instance_removed = False
                instance_added = False
                if instance_digits:
                    for p in participants_removed:
                        for ident in extract_participant_identifiers(p):
                            if normalize_digits(ident) == instance_digits:
                                instance_removed = True
                                break
                        if instance_removed:
                            break
                    
                    for p in participants_added:
                        for ident in extract_participant_identifiers(p):
                            if normalize_digits(ident) == instance_digits:
                                instance_added = True
                                break
                        if instance_added:
                            break
                
                # Atualizar conversa com nova lista de participantes
                with transaction.atomic():
                    updated_metadata = {
                        **conversation.group_metadata,
                        'participants': cleaned_participants,
                        'participants_count': len(cleaned_participants),
                        'participants_updated_at': timezone.now().isoformat(),
                    }
                    
                    # Se a instância saiu/entrou, atualizar flag no metadata
                    if instance_removed:
                        updated_metadata['instance_removed'] = True
                        updated_metadata['instance_removed_at'] = timezone.now().isoformat()
                    elif instance_added:
                        updated_metadata['instance_removed'] = False
                        updated_metadata['instance_removed_at'] = None
                    
                    conversation.group_metadata = updated_metadata
                    conversation.save(update_fields=['group_metadata'])
                    
                    logger.info(f"✅ [GROUP PARTICIPANTS] Conversa atualizada com {len(cleaned_participants)} participantes")
                
                # Preparar dados para broadcast
                added_names = []
                removed_names = []
                
                # Processar adicionados
                for p in participants_added:
                    if isinstance(p, dict):
                        name = p.get('name') or p.get('pushname') or p.get('phone', 'Usuário')
                        added_names.append(name)
                    elif isinstance(p, str):
                        added_names.append(p)
                
                # Processar removidos
                for p in participants_removed:
                    if isinstance(p, dict):
                        name = p.get('name') or p.get('pushname') or p.get('phone', 'Usuário')
                        removed_names.append(name)
                    elif isinstance(p, str):
                        removed_names.append(p)
                
                # ✅ Criar mensagens de sistema (notificações no grupo)
                try:
                    from apps.chat.models import Message
                    from apps.chat.utils.websocket import broadcast_message_received
                    
                    def create_system_message(content: str, event_type: str):
                        msg = Message.objects.create(
                            conversation=conversation,
                            content=content,
                            direction='incoming',
                            status='seen',
                            is_internal=True,
                            sender_name='Sistema',
                            metadata={'system_event': event_type}
                        )
                        broadcast_message_received(msg)
                    
                    if added_names:
                        added_text = ', '.join(added_names[:5])
                        if len(added_names) > 5:
                            added_text += f" e mais {len(added_names) - 5}"
                        create_system_message(f"👥 Entrou no grupo: {added_text}", 'group_participant_added')
                    
                    if removed_names:
                        removed_text = ', '.join(removed_names[:5])
                        if len(removed_names) > 5:
                            removed_text += f" e mais {len(removed_names) - 5}"
                        create_system_message(f"👥 Saiu do grupo: {removed_text}", 'group_participant_removed')
                    
                    if instance_removed:
                        create_system_message(
                            "🚫 Esta instância foi removida do grupo. Envio desativado.",
                            'group_instance_removed'
                        )
                    elif instance_added:
                        create_system_message(
                            "✅ Esta instância foi adicionada ao grupo. Envio reativado.",
                            'group_instance_added'
                        )
                except Exception as e:
                    logger.error(f"❌ [GROUP PARTICIPANTS] Erro ao criar mensagens de sistema: {e}", exc_info=True)
                
                # Enviar broadcast via WebSocket
                from apps.chat.utils.websocket import broadcast_to_tenant
                from apps.chat.api.serializers import ConversationSerializer
                
                conv_data = ConversationSerializer(conversation).data
                
                broadcast_to_tenant(
                    tenant_id=str(tenant.id),
                    event_type='group_participants_updated',
                    data={
                        'conversation': conv_data,
                        'conversation_id': str(conversation.id),
                        'added': added_names,
                        'removed': removed_names,
                        'added_count': len(participants_added),
                        'removed_count': len(participants_removed),
                        'total_participants': len(cleaned_participants)
                    }
                )
                
                logger.info(f"📡 [GROUP PARTICIPANTS] Broadcast enviado: +{len(participants_added)} -{len(participants_removed)}")
                
                return JsonResponse({
                    'status': 'success',
                    'event': 'group.participants.update',
                    'conversation_id': str(conversation.id),
                    'added_count': len(participants_added),
                    'removed_count': len(participants_removed),
                    'total_participants': len(cleaned_participants)
                })
                
            except Exception as e:
                logger.error(f"❌ [GROUP PARTICIPANTS] Erro ao processar: {e}", exc_info=True)
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
                
        except Exception as e:
            logger.error(f"❌ [GROUP PARTICIPANTS] Erro geral: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def handle_send_message(self, data):
        """Handle send.message events."""
        logger.info(f"📤 Message sent: {data.get('event')}")
        return JsonResponse({'status': 'success', 'event': 'send.message'})
    
    def handle_message_upsert(self, data):
        """Handle new messages from Evolution API."""
        try:
            # ✅ DEBUG CRÍTICO: Log quando messages.upsert chega
            logger.info(f"📥 [CONNECTIONS WEBHOOK] ====== messages.upsert RECEBIDO ======")
            logger.info(f"📥 [CONNECTIONS WEBHOOK] Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
            logger.info(f"📥 [CONNECTIONS WEBHOOK] Data completo: {data}")
            
            # ✅ FIX: Evolution API v2 envia 'data' como objeto, não lista
            # Estrutura: { event: 'messages.upsert', instance: '...', data: { key: {...}, message: {...} } }
            message_data = data.get('data', {})
            instance_name = data.get('instance', 'default')
            
            logger.info(f"📥 [CONNECTIONS WEBHOOK] Instance: {instance_name}")
            logger.info(f"📥 [CONNECTIONS WEBHOOK] Message data keys: {list(message_data.keys()) if isinstance(message_data, dict) else 'not dict'}")
            
            # ✅ FIX: Se data é um objeto (não lista), processar diretamente
            # Se for lista (formato antigo), processar primeiro item
            if isinstance(message_data, list):
                if len(message_data) == 0:
                    logger.warning(f"⚠️ [CONNECTIONS WEBHOOK] data está vazio (lista)")
                    return JsonResponse({'status': 'success', 'processed': 0})
                message_data = message_data[0]
                logger.info(f"📥 [CONNECTIONS WEBHOOK] data é LISTA, usando primeiro item")
            else:
                logger.info(f"📥 [CONNECTIONS WEBHOOK] data é OBJETO, processando diretamente")
            
            # 💬 FLOW CHAT: Processar mensagem para o chat em tempo real
            try:
                from apps.chat.webhooks import handle_message_upsert as chat_handle_message
                from apps.notifications.models import WhatsAppInstance
                from apps.connections.models import EvolutionConnection
                from django.db.models import Q
                
                # ✅ FIX CRÍTICO: Buscar WhatsAppInstance pelo instance_name (UUID) com default_department
                # Evolution API envia UUID (ex: "9afdad84-5411-4754-8f63-2599a6b9142c")
                whatsapp_instance = WhatsAppInstance.objects.select_related(
                    'tenant', 
                    'default_department'  # ✅ CRÍTICO: Carregar departamento padrão
                ).filter(
                    instance_name=instance_name,  # ✅ FIX: Buscar apenas por instance_name (UUID)
                    is_active=True,
                    status='active'
                ).first()
                
                # ✅ FALLBACK: Se não encontrou por instance_name, tentar por friendly_name
                if not whatsapp_instance:
                    whatsapp_instance = WhatsAppInstance.objects.select_related(
                        'tenant',
                        'default_department'
                    ).filter(
                        friendly_name=instance_name,
                        is_active=True,
                        status='active'
                    ).first()
                
                # Buscar EvolutionConnection para passar também
                connection = EvolutionConnection.objects.filter(is_active=True).select_related('tenant').first()
                
                if whatsapp_instance:
                    logger.info(f"✅ [FLOW CHAT] WhatsAppInstance encontrada: {whatsapp_instance.friendly_name} ({whatsapp_instance.instance_name})")
                    logger.info(f"   📋 Default Department: {whatsapp_instance.default_department.name if whatsapp_instance.default_department else 'Nenhum (Inbox)'}")
                    
                    # ✅ FIX: Passar wa_instance e connection para chat_handle_message
                    chat_handle_message(data, whatsapp_instance.tenant, connection=connection, wa_instance=whatsapp_instance)
                    logger.info(f"💬 [FLOW CHAT] Mensagem processada para tenant {whatsapp_instance.tenant.name}")
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] WhatsAppInstance não encontrada para instance: {instance_name}")
                    # ✅ FALLBACK: Tentar processar mesmo sem wa_instance (pode funcionar com connection)
                    if connection:
                        logger.info(f"⚠️ [FLOW CHAT] Processando com connection apenas (sem wa_instance)")
                        chat_handle_message(data, connection.tenant, connection=connection, wa_instance=None)
            except Exception as e:
                logger.error(f"❌ [FLOW CHAT] Erro ao processar mensagem: {e}", exc_info=True)
            
            # ✅ FIX: Processar mensagem para analytics/campaigns
            # Evolution API v2: data.data é objeto { key: {...}, message: {...} }
            # Evolution API v1: data.data.messages é lista [...]
            messages_list = data.get('data', {}).get('messages', [])
            if isinstance(messages_list, list) and len(messages_list) > 0:
                # Formato antigo (lista): processar cada item
                for msg_data in messages_list:
                    self.process_message(msg_data, instance_name)
                logger.info(f"✅ [CONNECTIONS WEBHOOK] Processadas {len(messages_list)} mensagens (formato lista)")
                return JsonResponse({'status': 'success', 'processed': len(messages_list)})
            else:
                # ✅ Formato novo (objeto): já foi processado pelo Flow Chat
                # Não precisa processar novamente para analytics (já foi feito no chat)
                logger.info(f"✅ [CONNECTIONS WEBHOOK] Mensagem processada pelo Flow Chat (formato objeto)")
                return JsonResponse({'status': 'success', 'processed': 1})
            
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
            # ✅ SECURITY FIX: Use settings instead of hardcoded credentials
            from django.conf import settings
            connection, created = EvolutionConnection.objects.get_or_create(
                name=f'Evolution {instance}',
                defaults={
                    'base_url': settings.EVOLUTION_API_URL,
                    'api_key': settings.EVOLUTION_API_KEY,
                    'webhook_url': f'{settings.BASE_URL}/api/webhooks/evolution/',
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
        logger.info(f"🔄 [WEBHOOK] handle_message_update INICIADO")
        try:
            update_data = data.get('data', {})
            instance_name = data.get('instance', 'default')
            
            logger.info(f"🔍 [WEBHOOK] instance_name: {instance_name}")
            logger.info(f"🔍 [WEBHOOK] update_data: {update_data}")
            
            # Extract message info from Evolution API structure
            chat_id = update_data.get('remoteJid', '')
            message_id = update_data.get('messageId', '')  # Evolution API field
            status = update_data.get('status', '').lower()  # Convert to lowercase
            key_id = update_data.get('keyId', '')
            
            logger.info(f"Message update: messageId={message_id}, keyId={key_id}, status={status}, chat_id={chat_id}")
            
            # 💬 FLOW CHAT: Atualizar status da mensagem no chat
            logger.info(f"🚀 [FLOW CHAT] Iniciando processamento do chat...")
            try:
                from apps.chat.webhooks import handle_message_update as chat_handle_update
                from apps.notifications.models import WhatsAppInstance
                from django.db.models import Q
                
                # Buscar instância - Evolution API envia o "nome da instância" (ex: "RBTec")
                # Pode ser friendly_name OU instance_name (depende da configuração)
                logger.info(f"🔍 [FLOW CHAT] Buscando WhatsAppInstance com: {instance_name}")
                
                instance = WhatsAppInstance.objects.select_related('tenant').filter(
                    Q(instance_name=instance_name) | Q(friendly_name=instance_name),
                    is_active=True
                ).first()
                
                if instance:
                    logger.info(f"✅ [FLOW CHAT] Instance encontrada: {instance.friendly_name} (UUID: {instance.instance_name}) - Tenant: {instance.tenant.name}")
                    chat_handle_update(data, instance.tenant)
                    logger.info(f"💬 [FLOW CHAT] Status atualizado para tenant {instance.tenant.name}")
                else:
                    logger.warning(f"⚠️ [FLOW CHAT] Nenhuma WhatsAppInstance ativa encontrada com: {instance_name}")
                    logger.warning(f"   Verifique se existe uma instância com instance_name='{instance_name}' OU friendly_name='{instance_name}'")
            except Exception as e:
                logger.error(f"❌ [FLOW CHAT] Erro ao atualizar status: {e}", exc_info=True)
            
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
                    # ✅ CORREÇÃO: Log apenas em debug (não é erro, pode ser mensagem do chat normal)
                    logger.debug(f"ℹ️ Trying with keyId instead: {key_id} (pode ser mensagem do chat normal)")
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
        # ✅ CORREÇÃO: Garantir que logger está no escopo local
        import logging
        from django.utils import timezone
        _logger = logging.getLogger(__name__)
        
        try:
            from apps.campaigns.models import CampaignContact
            
            _logger.info(f"🔍 [WEBHOOK] Buscando CampaignContact com message_id: {message_id}, status: {status}")
            
            # ✅ CORREÇÃO: Adicionar retry para race condition (webhook pode chegar antes do message_id ser salvo)
            campaign_contact = None
            max_retries = 5
            retry_delay = 0.3  # 300ms entre tentativas
            
            for attempt in range(max_retries):
                # Find campaign contact by WhatsApp message ID
                campaign_contact = CampaignContact.objects.filter(
                    whatsapp_message_id=message_id
                ).first()
                
                if campaign_contact:
                    break
                
                # Se não encontrou e ainda tem tentativas, aguardar um pouco
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    _logger.debug(f"⏳ [WEBHOOK] Aguardando whatsapp_message_id ser salvo (tentativa {attempt + 1}/{max_retries})...")
            
            if not campaign_contact:
                # Tentar buscar sem filtro para debug
                _logger.warning(f"⚠️ [WEBHOOK] CampaignContact não encontrado com message_id: {message_id} após {max_retries} tentativas")
                _logger.warning(f"   Tentando buscar por outros campos...")
                
                # Buscar contatos recentes para debug
                recent_contacts = CampaignContact.objects.filter(
                    sent_at__isnull=False
                ).order_by('-sent_at')[:5]
                
                _logger.warning(f"   Últimos 5 contatos enviados:")
                for cc in recent_contacts:
                    _logger.warning(f"     - ID: {cc.id}, message_id: {cc.whatsapp_message_id}, sent_at: {cc.sent_at}")
                
                return False
            
            _logger.info(f"✅ [WEBHOOK] CampaignContact encontrado: {campaign_contact.id} para message_id: {message_id}")
            _logger.info(f"   Status atual: {campaign_contact.status}")
            _logger.info(f"   delivered_at: {campaign_contact.delivered_at}")
            _logger.info(f"   read_at: {campaign_contact.read_at}")
            
            # Update status based on Evolution API status
            if status in ['sent', 'server_ack']:
                # ✅ NOVO: Tratar server_ack como mensagem enviada (mas ainda não entregue)
                if campaign_contact.status == 'sending':
                    campaign_contact.status = 'sent'
                    campaign_contact.sent_at = campaign_contact.sent_at or timezone.now()
                    _logger.info(f"✅ [WEBHOOK] Campaign contact {campaign_contact.id} marcado como enviado (status: {status})")
                    _logger.info(f"   Status final: {campaign_contact.status}, sent_at: {campaign_contact.sent_at}")
                else:
                    _logger.info(f"ℹ️ [WEBHOOK] Campaign contact {campaign_contact.id} já está em status {campaign_contact.status}, ignorando server_ack")
                
            elif status in ['delivered', 'delivery_ack']:
                campaign_contact.delivered_at = timezone.now()
                # ✅ CORREÇÃO: Só atualizar status para 'delivered' se ainda não foi lido
                if campaign_contact.status != 'read':
                    campaign_contact.status = 'delivered'
                _logger.info(f"✅ [WEBHOOK] Campaign contact {campaign_contact.id} marcado como entregue (status: {status})")
                _logger.info(f"   Status final: {campaign_contact.status}, delivered_at: {campaign_contact.delivered_at}")
                
            elif status in ['read', 'read_ack']:
                # Se ainda não foi entregue, marcar como entregue primeiro
                if not campaign_contact.delivered_at:
                    campaign_contact.delivered_at = timezone.now()
                    _logger.info(f"✅ [WEBHOOK] Campaign contact {campaign_contact.id} marcado como entregue antes de ler")
                campaign_contact.read_at = timezone.now()
                campaign_contact.status = 'read'
                _logger.info(f"✅ [WEBHOOK] Campaign contact {campaign_contact.id} marcado como lido (status: {status})")
                _logger.info(f"   Status final: {campaign_contact.status}, read_at: {campaign_contact.read_at}")
                
            elif status in ['failed', 'error']:
                campaign_contact.failed_at = timezone.now()
                campaign_contact.error_message = f"Message failed: {status}"
                campaign_contact.status = 'failed'
                _logger.info(f"❌ [WEBHOOK] Campaign contact {campaign_contact.id} marcado como falhou (status: {status})")
            
            else:
                _logger.warning(f"⚠️ [WEBHOOK] Status desconhecido recebido: {status}")
                return False
            
            # ✅ CORREÇÃO: Incluir sent_at nos campos de atualização se status for 'sent' ou 'server_ack'
            update_fields = ['status', 'delivered_at', 'read_at', 'failed_at', 'error_message']
            if status in ['sent', 'server_ack']:
                update_fields.append('sent_at')
            
            campaign_contact.save(update_fields=update_fields)
            _logger.info(f"✅ [WEBHOOK] CampaignContact salvo com sucesso. Status: {campaign_contact.status}")
            
            # 📊 ATUALIZAR LOG COM INFORMAÇÕES DE ENTREGA/LEITURA
            self.update_campaign_log(campaign_contact, status)
            
            # Update campaign stats
            self.update_campaign_stats(campaign_contact.campaign)
            
            # Update delivery status in the log
            from apps.campaigns.models import CampaignLog
            if status in ['delivered', 'delivery_ack']:
                CampaignLog.update_message_delivery_status(campaign_contact, 'delivered')
                _logger.info(f"✅ [WEBHOOK] Log de entrega processado")
            elif status in ['read', 'read_ack']:
                CampaignLog.update_message_delivery_status(campaign_contact, 'read')
                _logger.info(f"✅ [WEBHOOK] Log de leitura processado")
            elif status in ['sent', 'server_ack']:
                # ✅ NOVO: Criar log de envio se não existir (para casos onde webhook chega antes do log ser criado)
                existing_log = CampaignLog.objects.filter(
                    campaign_contact=campaign_contact,
                    log_type='message_sent'
                ).first()
                
                if not existing_log:
                    _logger.info(f"⚠️ [WEBHOOK] Log de envio não encontrado, criando...")
                    try:
                        CampaignLog.log_message_sent(
                            campaign=campaign_contact.campaign,
                            instance=campaign_contact.instance_used,
                            contact=campaign_contact.contact,
                            campaign_contact=campaign_contact,
                            whatsapp_message_id=message_id
                        )
                        _logger.info(f"✅ [WEBHOOK] Log de envio criado com sucesso")
                    except Exception as e:
                        _logger.error(f"❌ [WEBHOOK] Erro ao criar log de envio: {e}", exc_info=True)
            
            return True
                
        except Exception as e:
            # ✅ CORREÇÃO: Usar _logger local ao invés de logger global
            _logger.error(f"❌ [WEBHOOK] Erro ao atualizar campaign contact por message_id: {str(e)}", exc_info=True)
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
            # ✅ CORREÇÃO: logger já está definido no topo do arquivo, não precisa redefinir
            logger.error(f"Error updating campaign contact status: {str(e)}", exc_info=True)
    
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
            from django.db.models import Q
            
            total_contacts = CampaignContact.objects.filter(campaign=campaign).count()
            
            # ✅ CORREÇÃO: Contar enviadas como todas que têm sent_at OU status 'sent', 'delivered', 'read'
            sent_count = CampaignContact.objects.filter(
                campaign=campaign
            ).filter(
                Q(sent_at__isnull=False) | Q(status__in=['sent', 'delivered', 'read'])
            ).distinct().count()
            
            # ✅ CORREÇÃO: Contar como entregues: mensagens com delivered_at OU status 'delivered' OU 'read'
            delivered_count = CampaignContact.objects.filter(
                campaign=campaign
            ).filter(
                Q(delivered_at__isnull=False) | Q(status__in=['delivered', 'read'])
            ).distinct().count()
            
            # ✅ CORREÇÃO: Contar como lidas: mensagens com read_at OU status 'read'
            read_count = CampaignContact.objects.filter(
                campaign=campaign
            ).filter(
                Q(read_at__isnull=False) | Q(status='read')
            ).distinct().count()
            
            failed_count = CampaignContact.objects.filter(campaign=campaign, status='failed').count()
            
            # Atualizar campos da campanha
            campaign.messages_sent = sent_count
            campaign.messages_delivered = delivered_count
            campaign.messages_read = read_count
            campaign.messages_failed = failed_count
            campaign.save(update_fields=['messages_sent', 'messages_delivered', 'messages_read', 'messages_failed'])
            
            logger.info(f"✅ [WEBHOOK] Campaign {campaign.id} stats updated:")
            logger.info(f"   Total contacts: {total_contacts}")
            logger.info(f"   Sent: {sent_count}")
            logger.info(f"   Delivered: {delivered_count}")
            logger.info(f"   Read: {read_count}")
            logger.info(f"   Failed: {failed_count}")
            
        except Exception as e:
            logger.error(f"❌ [WEBHOOK] Error updating campaign stats: {str(e)}", exc_info=True)
    
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
                    logger.debug(f"ℹ️ No Message record found for campaign message {message_id} (pode ser mensagem do chat normal)")
                    return False
            else:
                # ✅ CORREÇÃO: Não é erro se não encontrar CampaignContact
                # A mensagem pode ser do chat normal (não de campanha)
                logger.debug(f"ℹ️ No CampaignContact found for message_id: {message_id} (pode ser mensagem do chat normal)")
                return False
                
        except Exception as e:
            logger.error(f"Error updating Message model by message_id: {str(e)}")
            return False

    def handle_connection_update(self, data):
        """Handle connection status updates."""
        try:
            instance_name = data.get('instance') or (data.get('data') or {}).get('instance')
            payload = data.get('data') or {}
            state = (payload.get('state') or '').lower()
            status_reason = payload.get('statusReason')

            if instance_name:
                set_instance_state(instance_name, payload)

            logger.info(
                "🔄 [EVOLUTION] connection.update recebido | instance=%s state=%s status_reason=%s",
                instance_name,
                state or 'unknown',
                status_reason,
            )

            if instance_name:
                from apps.notifications.models import WhatsAppInstance

                qs = WhatsAppInstance.objects.filter(instance_name=instance_name)
                updates = {
                    'last_check': timezone.now(),
                }

                if state == 'open':
                    updates.update({'connection_state': 'open', 'status': 'active', 'last_error': ''})
                elif state == 'connecting':
                    updates.update({'connection_state': 'connecting', 'status': 'inactive'})
                elif state:
                    updates.update({'connection_state': state, 'status': 'inactive'})

                if status_reason is not None:
                    updates['last_error'] = f"status_reason={status_reason}"

                if updates:
                    qs.update(**updates)

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
