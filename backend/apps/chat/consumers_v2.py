"""
WebSocket Consumer V2 para chat em tempo real.

ARQUITETURA NOVA:
- 1 conexão WebSocket por usuário (não por conversa)
- Subscribe/Unsubscribe para trocar entre conversas
- Escalável para 10-20+ conversas simultâneas
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


def _mask_remote_jid(jid: str) -> str:
    """Mascara JID para logs (segurança)."""
    if not jid:
        return 'N/A'
    if '@' in jid:
        parts = jid.split('@')
        phone = parts[0]
        domain = parts[1]
        if len(phone) > 4:
            return f"{phone[:2]}***{phone[-2:]}@{domain}"
        return f"***@{domain}"
    if len(jid) > 4:
        return f"{jid[:2]}***{jid[-2:]}"
    return "***"


class ChatConsumerV2(AsyncWebsocketConsumer):
    """
    Consumer WebSocket V2 - Modelo Global (1 conexão por usuário).
    
    Grupos:
    - chat_tenant_{tenant_id} (recebe todas as atualizações do tenant)
    - chat_tenant_{tenant_id}_conversation_{conversation_id} (conversa específica)
    
    Eventos:
    - subscribe: Cliente quer receber eventos de uma conversa
    - unsubscribe: Cliente para de receber eventos de uma conversa
    - send_message: Cliente envia mensagem
    - message_received: Servidor broadcast nova mensagem
    - message_status_update: Atualização de status (delivered/seen)
    - typing: Usuário está digitando
    """
    
    async def connect(self):
        """
        Aceita conexão WebSocket e adiciona ao grupo do tenant.
        Autentica via JWT no query string.
        """
        # Extrair e validar token JWT
        from urllib.parse import parse_qs
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        
        if not token:
            logger.warning(f"❌ [CHAT WS V2] Token JWT não fornecido")
            await self.close(code=4001)
            return
        
        # Autenticar usuário via token
        self.user = await self.authenticate_token(token)
        if not self.user:
            logger.warning(f"❌ [CHAT WS V2] Token JWT inválido")
            await self.close(code=4001)
            return
        
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.subscribed_conversations = set()  # Conversas que o usuário está ouvindo
        
        # Verifica se o usuário pertence ao tenant
        if str(self.user.tenant_id) != self.tenant_id:
            logger.warning(
                f"❌ [CHAT WS V2] Usuário {self.user.email} tentou acessar tenant diferente"
            )
            await self.close(code=4003)
            return
        
        # Nome do grupo do tenant (para receber notificações globais)
        self.tenant_group_name = f"chat_tenant_{self.tenant_id}"
        
        # Adiciona ao grupo do tenant
        await self.channel_layer.group_add(
            self.tenant_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(
            f"✅ [CHAT WS V2] Usuário {self.user.email} conectado ao tenant {self.tenant_id}"
        )
    
    async def disconnect(self, close_code):
        """Remove de todos os grupos ao desconectar."""
        # Remove do grupo do tenant
        if hasattr(self, 'tenant_group_name'):
            await self.channel_layer.group_discard(
                self.tenant_group_name,
                self.channel_name
            )
        
        # Remove de todas as conversas subscritas (se existir o atributo)
        if hasattr(self, 'subscribed_conversations') and self.subscribed_conversations:
            for conversation_id in self.subscribed_conversations:
                room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
                await self.channel_layer.group_discard(
                    room_group_name,
                    self.channel_name
                )
        
        # Log de desconexão (com verificação de atributos)
        user_email = getattr(self, 'user', None)
        user_email = user_email.email if user_email and hasattr(user_email, 'email') else 'desconhecido'
        conversations_count = len(self.subscribed_conversations) if hasattr(self, 'subscribed_conversations') else 0
        logger.info(
            f"🔌 [CHAT WS V2] Usuário {user_email} desconectado (tinha {conversations_count} conversas subscritas)"
        )
    
    async def receive(self, text_data):
        """
        Recebe mensagem do cliente e processa.
        """
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            # ✅ LOG CRÍTICO: Logar TODAS as mensagens recebidas
            logger.info(f"📨 [CHAT WS V2] Mensagem recebida do cliente:")
            logger.info(f"   Event type: {event_type}")
            logger.info(f"   Data completo: {data}")
            
            if event_type == 'subscribe':
                await self.handle_subscribe(data)
            elif event_type == 'unsubscribe':
                await self.handle_unsubscribe(data)
            elif event_type == 'send_message':
                await self.handle_send_message(data)
            elif event_type == 'typing':
                await self.handle_typing(data)
            elif event_type == 'mark_as_seen':
                await self.handle_mark_as_seen(data)
            else:
                logger.warning(f"⚠️ [CHAT WS V2] Tipo de evento desconhecido: {event_type}")
        
        except json.JSONDecodeError:
            logger.error(f"❌ [CHAT WS V2] JSON inválido recebido")
        except Exception as e:
            logger.error(f"❌ [CHAT WS V2] Erro ao processar mensagem: {e}", exc_info=True)
    
    async def handle_subscribe(self, data):
        """
        Cliente quer receber eventos de uma conversa específica.
        """
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            logger.warning(f"⚠️ [CHAT WS V2] Subscribe sem conversation_id")
            return
        
        # Verifica se o usuário tem acesso à conversa
        has_access = await self.check_conversation_access(conversation_id)
        if not has_access:
            logger.warning(
                f"❌ [CHAT WS V2] Usuário {self.user.email} sem acesso à conversa {conversation_id}"
            )
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Sem acesso à conversa',
                'conversation_id': conversation_id
            }))
            return
        
        # Adiciona ao grupo da conversa
        room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
        await self.channel_layer.group_add(
            room_group_name,
            self.channel_name
        )
        
        self.subscribed_conversations.add(conversation_id)
        
        logger.info(
            f"📥 [CHAT WS V2] Usuário {self.user.email} subscrito à conversa {conversation_id}"
        )
        
        # Confirma subscrição
        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'conversation_id': conversation_id
        }))
    
    async def handle_unsubscribe(self, data):
        """
        Cliente para de receber eventos de uma conversa.
        """
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            return
        
        if conversation_id in self.subscribed_conversations:
            # Remove do grupo da conversa
            room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
            await self.channel_layer.group_discard(
                room_group_name,
                self.channel_name
            )
            
            self.subscribed_conversations.remove(conversation_id)
            
            logger.info(
                f"📤 [CHAT WS V2] Usuário {self.user.email} desinscrito da conversa {conversation_id}"
            )
    
    async def handle_send_message(self, data):
        """
        Processa envio de mensagem do cliente.
        
        ✅ SEGURANÇA CRÍTICA: conversation_id é OBRIGATÓRIO
        NUNCA usar fallback para última conversa subscrita - isso pode enviar mensagem para destinatário errado!
        """
        # ✅ CORREÇÃO CRÍTICA: conversation_id é OBRIGATÓRIO - NUNCA usar fallback
        conversation_id = data.get('conversation_id')
        
        # ✅ LOG CRÍTICO: Verificar se conversation_id foi fornecido
        logger.critical(f"📥 [CHAT WS V2] ====== RECEBENDO send_message ======")
        logger.critical(f"   conversation_id recebido: {conversation_id}")
        logger.critical(f"   conversation_id tipo: {type(conversation_id)}")
        logger.critical(f"   conversation_id existe? {bool(conversation_id)}")
        logger.critical(f"   subscribed_conversations: {list(self.subscribed_conversations)}")
        logger.critical(f"   Data completo: {json.dumps(data, indent=2, default=str)}")
        
        # ✅ VALIDAÇÃO CRÍTICA: conversation_id é OBRIGATÓRIO
        if not conversation_id:
            error_msg = '❌ [SEGURANÇA] conversation_id é OBRIGATÓRIO! Mensagem rejeitada para prevenir envio para destinatário errado.'
            logger.critical(error_msg)
            logger.critical(f"   subscribed_conversations disponíveis: {list(self.subscribed_conversations)}")
            logger.critical(f"   Data recebido: {json.dumps(data, indent=2, default=str)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'conversation_id é obrigatório',
                'error_code': 'MISSING_CONVERSATION_ID'
            }))
            return
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se conversation_id é válido (UUID)
        try:
            from uuid import UUID
            UUID(str(conversation_id))  # Valida formato UUID
        except (ValueError, TypeError):
            error_msg = f'❌ [SEGURANÇA] conversation_id inválido: {conversation_id}'
            logger.critical(error_msg)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'conversation_id inválido',
                'error_code': 'INVALID_CONVERSATION_ID'
            }))
            return
        
        content = data.get('content', '').strip()
        is_internal = data.get('is_internal', False)
        attachment_urls = data.get('attachment_urls', [])
        include_signature = data.get('include_signature', True)  # ✅ Por padrão inclui assinatura
        reply_to = data.get('reply_to')  # ✅ NOVO: ID da mensagem sendo respondida
        mentions = data.get('mentions', [])  # ✅ NOVO: Lista de números mencionados
        
        # ✅ LOG CRÍTICO: Confirmar conversation_id que será usado
        logger.critical(f"✅ [CHAT WS V2] conversation_id validado: {conversation_id}")
        logger.critical(f"   content: {content[:50]}...")
        logger.critical(f"   reply_to recebido: {reply_to}")
        logger.critical(f"   mentions: {mentions}")
        
        if not content and not attachment_urls:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Mensagem vazia'
            }))
            return
        
        # Cria mensagem no banco
        message = await self.create_message(
            conversation_id=conversation_id,
            content=content,
            is_internal=is_internal,
            attachment_urls=attachment_urls,
            include_signature=include_signature,
            reply_to=reply_to,  # ✅ NOVO: Passar reply_to
            mentions=mentions  # ✅ NOVO: Passar mentions
        )
        
        if not message:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Erro ao criar mensagem'
            }))
            return
        
        # Envia para RabbitMQ para processamento assíncrono
        await self.enqueue_message_for_evolution(message)
        
        # Broadcast imediato como pendente
        await self.broadcast_pending_message(message)
 
    async def handle_typing(self, data):
        """
        Broadcast de status 'digitando'.
        """
        conversation_id = data.get('conversation_id')
        if not conversation_id or conversation_id not in self.subscribed_conversations:
            return
        
        is_typing = data.get('is_typing', False)
        
        room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
        await self.channel_layer.group_send(
            room_group_name,
            {
                'type': 'typing_status',
                'user_id': str(self.user.id),
                'user_email': self.user.email,
                'is_typing': is_typing
            }
        )
    
    async def handle_mark_as_seen(self, data):
        """
        Marca mensagem como vista.
        """
        message_id = data.get('message_id')
        conversation_id = data.get('conversation_id')
        
        if not message_id or not conversation_id:
            return
        
        success = await self.mark_message_as_seen(message_id, conversation_id)
        
        if success:
            room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
            await self.channel_layer.group_send(
                room_group_name,
                {
                    'type': 'message_status_update',
                    'message_id': message_id,
                    'status': 'seen'
                }
            )
    
    # Handlers de eventos do grupo
    
    async def message_received(self, event):
        """Broadcast nova mensagem."""
        # ✅ DEBUG: Logar recebimento de evento
        logger.info(f"📨 [CHAT WS V2] message_received recebido do grupo")
        logger.info(f"   Event keys: {list(event.keys())}")
        logger.info(f"   Message ID: {event.get('message', {}).get('id', 'N/A')}")
        logger.info(f"   Conversation ID: {event.get('conversation_id', 'N/A')}")
        
        await self.send(text_data=json.dumps({
            'type': 'message_received',
            'message': event['message']
        }))
        
        logger.info(f"✅ [CHAT WS V2] message_received enviado para frontend")
    
    async def message_status_update(self, event):
        """Broadcast atualização de status."""
        await self.send(text_data=json.dumps({
            'type': 'message_status_update',
            'message_id': event['message_id'],
            'status': event['status']
        }))
    
    async def campaign_update(self, event):
        """Broadcast atualização de campanha."""
        # ✅ NOVO: Handler para mensagens do tipo campaign_update
        await self.send(text_data=json.dumps({
            'type': 'campaign_update',
            'payload': event.get('payload', {})
        }))
    
    async def typing_status(self, event):
        """Broadcast status de digitando."""
        # Não envia para o próprio usuário
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_email': event['user_email'],
                'is_typing': event['is_typing']
            }))
    
    async def new_conversation(self, event):
        """Broadcast quando uma nova conversa é criada (Inbox)."""
        await self.send(text_data=json.dumps({
            'type': 'new_conversation',
            'conversation': event['conversation']
        }))
    
    async def new_message_notification(self, event):
        """Broadcast quando há nova mensagem em conversa existente."""
        await self.send(text_data=json.dumps({
            'type': 'new_message_notification',
            'conversation': event.get('conversation'),
            'message': event.get('message')
        }))
    
    async def mention_notification(self, event):
        """✅ MELHORIA: Handler para notificações de menção."""
        message_data = event.get('message', {})
        logger.info(f"📬 [CHAT WS V2] Notificação de menção recebida para usuário {self.user.email}")
        await self.send(text_data=json.dumps({
            'type': 'mention_notification',
            'message': {
                'id': message_data.get('id'),
                'conversation_id': message_data.get('conversation_id'),
                'content': message_data.get('content', ''),
                'sender_name': message_data.get('sender_name', 'Usuário'),
                'conversation_name': message_data.get('conversation_name', 'Conversa')
            }
        }))
    
    async def conversation_updated(self, event):
        """Broadcast quando conversa é atualizada."""
        await self.send(text_data=json.dumps({
            'type': 'conversation_updated',
            'conversation': event.get('conversation')
        }))
    
    # Database queries (sync_to_async)
    
    @database_sync_to_async
    def authenticate_token(self, token):
        """Autentica usuário via token JWT."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            User = get_user_model()
            user = User.objects.select_related('tenant').get(id=user_id)
            
            return user
        
        except Exception as e:
            logger.error(f"❌ [CHAT WS V2] Erro ao autenticar token: {e}")
            return None
    
    @database_sync_to_async
    def check_conversation_access(self, conversation_id):
        """Verifica se o usuário tem acesso à conversa."""
        from apps.chat.models import Conversation
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            
            # ✅ SEGURANÇA CRÍTICA: Verificar tenant PRIMEIRO
            # Mesmo superusers devem ter tenant associado para operações normais
            if not self.user.tenant:
                logger.warning(
                    f"🚨 [SEGURANÇA WS] Usuário {self.user.email} sem tenant tentou acessar conversa {conversation_id}"
                )
                return False
            
            # Verifica tenant (aplicado para TODOS, incluindo superusers)
            if conversation.tenant_id != self.user.tenant_id:
                logger.warning(
                    f"🚨 [SEGURANÇA WS] Tentativa de acesso a conversa de outro tenant! "
                    f"Usuário: {self.user.email} (tenant: {self.user.tenant_id}), "
                    f"Conversa: {conversation_id} (tenant: {conversation.tenant_id})"
                )
                return False
            
            # Superuser com tenant correto pode tudo
            if self.user.is_superuser:
                return True
            
            # Admin do tenant pode tudo
            if self.user.is_admin:
                return True
            
            # Gerente/Agente: verifica departamento OU conversa pending (Inbox)
            if self.user.is_gerente or self.user.is_agente:
                if conversation.department_id is None:
                    return True
                else:
                    return self.user.departments.filter(id=conversation.department_id).exists()
            
            return False
        
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def create_message(self, conversation_id, content, is_internal, attachment_urls, include_signature=True, reply_to=None, mentions=None):
        """
        Cria mensagem no banco.
        
        ✅ SEGURANÇA CRÍTICA: Valida que conversation existe e pertence ao tenant do usuário
        """
        from apps.chat.models import Message, Conversation
        
        try:
            # ✅ VALIDAÇÃO CRÍTICA: Buscar conversa e garantir que pertence ao tenant do usuário
            conversation = Conversation.objects.select_related('tenant').get(
                id=conversation_id,
                tenant=self.tenant  # ✅ CRÍTICO: Garantir que conversa pertence ao tenant do usuário
            )
            
            # ✅ LOG CRÍTICO: Confirmar conversa encontrada
            logger.critical(f"✅ [CHAT WS V2] Conversa validada: {conversation.id}")
            logger.critical(f"   tenant: {conversation.tenant.name if conversation.tenant else 'N/A'}")
            logger.critical(f"   contact_phone: {_mask_remote_jid(conversation.contact_phone) if conversation.contact_phone else 'N/A'}")
            logger.critical(f"   conversation_type: {conversation.conversation_type}")
            logger.critical(f"   contact_name: {conversation.contact_name or 'N/A'}")
            
            # Preparar metadata
            metadata = {
                'include_signature': include_signature  # ✅ Flag para assinatura
            }
            if attachment_urls:
                metadata['attachment_urls'] = attachment_urls
            
            # ✅ NOVO: Adicionar reply_to no metadata se fornecido
            if reply_to:
                metadata['reply_to'] = reply_to
                logger.info(f"💬 [CHAT WS V2] Reply_to adicionado ao metadata: {reply_to}")
            else:
                logger.debug(f"💬 [CHAT WS V2] Nenhum reply_to fornecido")
            
            # ✅ NOVO: Processar menções se for grupo
            if mentions and conversation.conversation_type == 'group':
                # Validar números e buscar nomes dos participantes
                processed_mentions = []
                group_metadata = conversation.group_metadata or {}
                participants = group_metadata.get('participants', [])
                
                # Criar mapa de telefone -> nome para busca rápida
                phone_to_name = {p.get('phone', ''): p.get('name', '') for p in participants}
                
                for phone in mentions:
                    # Normalizar telefone (remover + e espaços)
                    clean_phone = phone.replace('+', '').replace(' ', '').strip()
                    name = phone_to_name.get(clean_phone, '')
                    
                    processed_mentions.append({
                        'phone': clean_phone,
                        'name': name or clean_phone
                    })
                
                metadata['mentions'] = processed_mentions
            
            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                direction='outgoing',
                status='pending',
                is_internal=is_internal,
                metadata=metadata
            )
            
            return message
        
        except Exception as e:
            logger.error(f"❌ [CHAT WS V2] Erro ao criar mensagem: {e}", exc_info=True)
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serializa mensagem para JSON."""
        from apps.chat.utils.serialization import serialize_message_for_ws
        return serialize_message_for_ws(message)
    
    @database_sync_to_async
    def serialize_conversation(self, conversation):
        """Serializa conversa para JSON."""
        from apps.chat.utils.serialization import serialize_conversation_for_ws
        return serialize_conversation_for_ws(conversation)
    
    async def broadcast_pending_message(self, message):
        """Broadcast imediato para mostrar mensagem como pendente."""
        message_data = await self.serialize_message(message)
        
        # ✅ DEBUG: Logar metadata.reply_to se existir
        if message_data.get('metadata', {}).get('reply_to'):
            logger.info(f"💬 [CHAT WS V2] Broadcast mensagem com reply_to: {message_data['metadata']['reply_to']}")
        
        conversation_data = await self.serialize_conversation(message.conversation)

        conversation_id = str(message.conversation_id)
        room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
        tenant_group = f"chat_tenant_{self.tenant_id}"

        await self.channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data
            }
        )

        await self.channel_layer.group_send(
            tenant_group,
            {
                'type': 'message_received',
                'message': message_data,
                'conversation': conversation_data
            }
        )

        await self.channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_status_update',
                'message_id': str(message.id),
                'status': message.status or 'pending'
            }
        )

    @database_sync_to_async
    def mark_message_as_seen(self, message_id, conversation_id):
        """Marca mensagem como vista."""
        from apps.chat.models import Message
        
        try:
            message = Message.objects.get(id=message_id, conversation_id=conversation_id)
            if message.direction == 'incoming':
                message.status = 'seen'
                message.save(update_fields=['status'])
                return True
        except Message.DoesNotExist:
            pass
        
        return False
    
    @database_sync_to_async
    def enqueue_message_for_evolution(self, message):
        """Enfileira mensagem para envio via Evolution API."""
        from apps.chat.tasks import send_message_to_evolution
        logger.critical(f"📤 [CHAT WS V2] ====== ENFILEIRANDO MENSAGEM PARA ENVIO ======")
        logger.critical(f"   Message ID: {message.id}")
        logger.critical(f"   Content: {message.content[:50] if message.content else 'N/A'}...")
        logger.critical(f"   Metadata completo: {message.metadata}")
        reply_to = message.metadata.get('reply_to') if message.metadata else None
        logger.critical(f"   Reply to no metadata: {reply_to}")
        logger.critical(f"   Reply to existe? {bool(reply_to)}")
        logger.critical(f"   Reply to tipo: {type(reply_to)}")
        send_message_to_evolution.delay(str(message.id))
        logger.critical(f"✅ [CHAT WS V2] Mensagem {message.id} enfileirada com sucesso!")
    
    # ========== HANDLERS PARA BROADCASTS ==========
    
    async def chat_message(self, event):
        """
        Handler para broadcasts de novas mensagens.
        Enviado quando alguém envia uma mensagem (via API ou WebSocket).
        """
        # Extrair mensagem do event
        message_data = event.get('message')
        
        if message_data:
            # Enviar para o cliente WebSocket
            await self.send(text_data=json.dumps({
                'type': 'message_received',
                'message': message_data
            }))
            logger.debug(f"📨 [CHAT WS V2] Broadcast de mensagem enviado para {self.user.email}")
    
    async def message_status_update(self, event):
        """
        Handler para atualizações de status de mensagem.
        """
        await self.send(text_data=json.dumps({
            'type': 'message_status_update',
            'message_id': event.get('message_id'),
            'status': event.get('status')
        }))
    
    async def typing_status(self, event):
        """
        Handler para status de digitação.
        """
        await self.send(text_data=json.dumps({
            'type': 'typing_status',
            'user_email': event.get('user_email'),
            'is_typing': event.get('is_typing'),
            'conversation_id': event.get('conversation_id')
        }))
    
    async def attachment_downloaded(self, event):
        """
        Handler para broadcast quando anexo termina de baixar.
        Frontend recebe mensagem atualizada com file_url local.
        """
        await self.send(text_data=json.dumps({
            'type': 'attachment_downloaded',
            'message': event['message'],
            'attachment_id': event['attachment_id']
        }))
        logger.info(f"📡 [CHAT WS V2] Notificação de anexo baixado enviada")
    
    async def attachment_updated(self, event):
        """
        Handler para broadcast quando anexo é processado (S3 + cache Redis).
        Frontend recebe atualização com file_url proxy.
        """
        data = event.get('data', {})
        await self.send(text_data=json.dumps({
            'type': 'attachment_updated',
            'data': {
                'message_id': data.get('message_id'),
                'attachment_id': data.get('attachment_id'),
                'file_url': data.get('file_url'),
                'thumbnail_url': data.get('thumbnail_url'),
                'mime_type': data.get('mime_type'),
                'file_type': data.get('file_type'),
                'metadata': data.get('metadata', {})  # ✅ Incluir metadata (sem flag processing)
            }
        }))
        logger.info(f"📡 [CHAT WS V2] Notificação de anexo atualizado enviada (attachment_id: {data.get('attachment_id')})")
    
    async def message_reaction_update(self, event):
        """
        Handler para atualizações de reações de mensagem.
        Frontend recebe mensagem atualizada com reações.
        """
        await self.send(text_data=json.dumps({
            'type': 'message_reaction_update',
            'message': event.get('message'),
            'reaction': event.get('reaction')
        }))
        logger.debug(f"👍 [CHAT WS V2] Broadcast de reação enviado para {self.user.email}")

    async def message_deleted(self, event):
        """
        Handler para quando uma mensagem é apagada.
        Frontend recebe evento de mensagem apagada.
        """
        message_data = event.get('message', {})
        message_id = message_data.get('id') if isinstance(message_data, dict) else event.get('message_id')
        conversation_id = event.get('conversation_id')
        
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message': message_data,
            'message_id': message_id,
            'conversation_id': conversation_id
        }))
        logger.debug(f"🗑️ [CHAT WS V2] Broadcast de mensagem apagada enviado para {getattr(self, 'user', {}).email if hasattr(self, 'user') else 'desconhecido'}")

