"""
WebSocket Consumer para chat em tempo real.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para chat em tempo real.
    
    Grupos:
    - chat_tenant_{tenant_id}_conversation_{conversation_id}
    
    Eventos:
    - join_conversation: Cliente se conecta
    - send_message: Cliente envia mensagem
    - message_received: Servidor broadcast nova mensagem
    - message_status_update: Atualização de status (delivered/seen)
    - typing: Usuário está digitando
    """
    
    async def connect(self):
        """
        Aceita conexão WebSocket e adiciona ao grupo da conversa.
        Autentica via JWT no query string.
        """
        # Extrair e validar token JWT
        from urllib.parse import parse_qs
        query_string = self.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        
        if not token:
            logger.warning(f"❌ [CHAT WS] Token JWT não fornecido")
            await self.close(code=4001)
            return
        
        # Autenticar usuário via token
        self.user = await self.authenticate_token(token)
        if not self.user:
            logger.warning(f"❌ [CHAT WS] Token JWT inválido")
            await self.close(code=4001)
            return
        
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        
        # Nome do grupo
        self.room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{self.conversation_id}"
        
        # Verifica se o usuário tem acesso à conversa
        has_access = await self.check_conversation_access()
        if not has_access:
            logger.warning(
                f"❌ [CHAT WS] Usuário {self.user.email} sem acesso à conversa {self.conversation_id}"
            )
            await self.close(code=4003)
            return
        
        # Adiciona ao grupo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(
            f"✅ [CHAT WS] Usuário {self.user.email} conectado à conversa {self.conversation_id}"
        )
        
        # Notifica grupo
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': str(self.user.id),
                'user_email': self.user.email,
            }
        )
    
    async def disconnect(self, close_code):
        """Remove do grupo ao desconectar."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(
                f"🔌 [CHAT WS] Usuário {self.user.email} desconectado da conversa {self.conversation_id}"
            )
    
    async def receive(self, text_data):
        """
        Recebe mensagem do cliente e processa.
        """
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            if event_type == 'send_message':
                await self.handle_send_message(data)
            elif event_type == 'typing':
                await self.handle_typing(data)
            elif event_type == 'mark_as_seen':
                await self.handle_mark_as_seen(data)
            else:
                logger.warning(f"⚠️ [CHAT WS] Tipo de evento desconhecido: {event_type}")
        
        except json.JSONDecodeError:
            logger.error(f"❌ [CHAT WS] JSON inválido recebido")
        except Exception as e:
            logger.error(f"❌ [CHAT WS] Erro ao processar mensagem: {e}", exc_info=True)
    
    async def handle_send_message(self, data):
        """
        Processa envio de mensagem do cliente.
        Cria Message no banco e envia para RabbitMQ.
        """
        content = data.get('content', '').strip()
        is_internal = data.get('is_internal', False)
        attachment_urls = data.get('attachment_urls', [])
        
        if not content and not attachment_urls:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Mensagem vazia'
            }))
            return
        
        # Cria mensagem no banco
        message = await self.create_message(
            content=content,
            is_internal=is_internal,
            attachment_urls=attachment_urls
        )
        
        if not message:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Erro ao criar mensagem'
            }))
            return
        
        # Envia para RabbitMQ para processamento assíncrono
        await self.enqueue_message_for_evolution(message)
        
        # Broadcast para grupo
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message_received',
                'message': await self.serialize_message(message)
            }
        )
    
    async def handle_typing(self, data):
        """
        Broadcast de status 'digitando'.
        """
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
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
        if not message_id:
            return
        
        success = await self.mark_message_as_seen(message_id)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_status_update',
                    'message_id': message_id,
                    'status': 'seen'
                }
            )
    
    # Handlers de eventos do grupo
    
    async def user_joined(self, event):
        """Broadcast quando usuário entra."""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'user_email': event['user_email']
        }))
    
    async def message_received(self, event):
        """Broadcast nova mensagem."""
        await self.send(text_data=json.dumps({
            'type': 'message_received',
            'message': event['message']
        }))
    
    async def message_status_update(self, event):
        """Broadcast atualização de status."""
        await self.send(text_data=json.dumps({
            'type': 'message_status_update',
            'message_id': event['message_id'],
            'status': event['status']
        }))
    
    async def typing_status(self, event):
        """Broadcast status de digitando."""
        # Não envia para o próprio usuário
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'user_id': event['user_id'],
                'user_email': event['user_email'],
                'is_typing': event['is_typing']
            }))
    
    async def conversation_transferred(self, event):
        """Broadcast quando conversa é transferida."""
        await self.send(text_data=json.dumps({
            'type': 'conversation_transferred',
            'conversation_id': event['conversation_id'],
            'new_agent': event.get('new_agent'),
            'new_department': event.get('new_department'),
            'transferred_by': event.get('transferred_by')
        }))
    
    # Database queries (sync_to_async)
    
    @database_sync_to_async
    def authenticate_token(self, token):
        """
        Autentica usuário via token JWT.
        
        Args:
            token: Token JWT string
        
        Returns:
            User instance ou None
        """
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            
            # Validar token
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            # Buscar usuário
            User = get_user_model()
            user = User.objects.select_related('tenant').get(id=user_id)
            
            return user
        
        except Exception as e:
            logger.error(f"❌ [CHAT WS] Erro ao autenticar token: {e}")
            return None
    
    @database_sync_to_async
    def check_conversation_access(self):
        """Verifica se o usuário tem acesso à conversa."""
        from apps.chat.models import Conversation
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            # Superuser pode tudo
            if self.user.is_superuser:
                return True
            
            # Verifica tenant
            if conversation.tenant_id != self.user.tenant_id:
                return False
            
            # Admin do tenant pode tudo
            if self.user.is_admin:
                return True
            
            # Gerente/Agente: verifica departamento
            if self.user.is_gerente or self.user.is_agente:
                return self.user.departments.filter(id=conversation.department_id).exists()
            
            return False
        
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def create_message(self, content, is_internal, attachment_urls):
        """Cria mensagem no banco."""
        from apps.chat.models import Message, Conversation
        
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            
            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                direction='outgoing',
                status='pending',
                is_internal=is_internal
            )
            
            if attachment_urls:
                message.metadata = {'attachment_urls': attachment_urls}
                message.save(update_fields=['metadata'])
            
            return message
        
        except Exception as e:
            logger.error(f"❌ [CHAT WS] Erro ao criar mensagem: {e}", exc_info=True)
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serializa mensagem para JSON."""
        from apps.chat.api.serializers import MessageSerializer
        return MessageSerializer(message).data
    
    @database_sync_to_async
    def mark_message_as_seen(self, message_id):
        """Marca mensagem como vista."""
        from apps.chat.models import Message
        
        try:
            message = Message.objects.get(id=message_id, conversation_id=self.conversation_id)
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
        send_message_to_evolution.delay(str(message.id))

