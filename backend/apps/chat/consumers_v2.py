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
        
        # Remove de todas as conversas subscritas
        for conversation_id in self.subscribed_conversations:
            room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
            await self.channel_layer.group_discard(
                room_group_name,
                self.channel_name
            )
        
        logger.info(
            f"🔌 [CHAT WS V2] Usuário {self.user.email} desconectado (tinha {len(self.subscribed_conversations)} conversas subscritas)"
        )
    
    async def receive(self, text_data):
        """
        Recebe mensagem do cliente e processa.
        """
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
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
        """
        # Precisa saber qual conversa está ativa (última subscrita)
        # Podemos pegar do data ou assumir que só há 1 ativa por vez
        conversation_id = data.get('conversation_id')
        if not conversation_id:
            # Se não especificado, usar última subscrita
            if not self.subscribed_conversations:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Nenhuma conversa ativa'
                }))
                return
            # Pega a última (Python 3.7+ sets mantêm ordem de inserção)
            conversation_id = list(self.subscribed_conversations)[-1]
        
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
            conversation_id=conversation_id,
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
        
        # Broadcast para grupo da conversa
        room_group_name = f"chat_tenant_{self.tenant_id}_conversation_{conversation_id}"
        await self.channel_layer.group_send(
            room_group_name,
            {
                'type': 'message_received',
                'message': await self.serialize_message(message)
            }
        )
    
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
            
            # Superuser pode tudo
            if self.user.is_superuser:
                return True
            
            # Verifica tenant
            if conversation.tenant_id != self.user.tenant_id:
                return False
            
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
    def create_message(self, conversation_id, content, is_internal, attachment_urls):
        """Cria mensagem no banco."""
        from apps.chat.models import Message, Conversation
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            
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
            logger.error(f"❌ [CHAT WS V2] Erro ao criar mensagem: {e}", exc_info=True)
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serializa mensagem para JSON."""
        from apps.chat.api.serializers import MessageSerializer
        import uuid
        
        data = MessageSerializer(message).data
        
        def convert_uuids(obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids(item) for item in obj]
            return obj
        
        return convert_uuids(data)
    
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
        send_message_to_evolution.delay(str(message.id))

