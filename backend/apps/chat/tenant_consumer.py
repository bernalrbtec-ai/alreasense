"""
WebSocket Consumer para eventos globais do tenant (novas conversas, etc)
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class TenantChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para eventos do tenant inteiro.
    
    Grupos:
    - chat_tenant_{tenant_id}
    
    Eventos:
    - new_conversation: Nova conversa criada (Inbox)
    - conversation_updated: Conversa atualizada
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
            logger.warning(f"❌ [TENANT WS] Token JWT não fornecido")
            await self.close(code=4001)
            return
        
        # Autenticar usuário via token
        self.user = await self.authenticate_token(token)
        if not self.user:
            logger.warning(f"❌ [TENANT WS] Token JWT inválido")
            await self.close(code=4001)
            return
        
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        
        # Verificar se o usuário pertence ao tenant
        if str(self.user.tenant_id) != str(self.tenant_id):
            logger.warning(
                f"❌ [TENANT WS] Usuário {self.user.email} não pertence ao tenant {self.tenant_id}"
            )
            await self.close(code=4003)
            return
        
        # Nome do grupo
        self.room_group_name = f"chat_tenant_{self.tenant_id}"
        
        # Adiciona ao grupo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(
            f"✅ [TENANT WS] Usuário {self.user.email} conectado ao grupo do tenant {self.tenant_id}"
        )
    
    async def disconnect(self, close_code):
        """Remove do grupo ao desconectar."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(
                f"🔌 [TENANT WS] Usuário {self.user.email} desconectado do grupo do tenant"
            )
    
    async def receive(self, text_data):
        """
        Recebe mensagem do cliente.
        Por enquanto, apenas log - sem ações necessárias.
        """
        try:
            data = json.loads(text_data)
            logger.info(f"📥 [TENANT WS] Mensagem recebida: {data}")
        except json.JSONDecodeError:
            logger.error(f"❌ [TENANT WS] JSON inválido recebido")
    
    # Handlers de eventos do grupo
    
    async def new_conversation(self, event):
        """Broadcast quando uma nova conversa é criada."""
        await self.send(text_data=json.dumps({
            'type': 'new_conversation',
            'conversation': event['conversation']
        }))
        logger.info(f"🆕 [TENANT WS] Nova conversa enviada para cliente")
    
    async def new_message_notification(self, event):
        """Broadcast de nova mensagem em conversa existente."""
        await self.send(text_data=json.dumps({
            'type': 'new_message_notification',
            'conversation': event['conversation'],
            'message': event['message']
        }))
        logger.info(f"💬 [TENANT WS] Notificação de nova mensagem enviada")
    
    async def conversation_updated(self, event):
        """Broadcast quando uma conversa é atualizada."""
        await self.send(text_data=json.dumps({
            'type': 'conversation_updated',
            'conversation': event['conversation']
        }))
        logger.info(f"🔄 [TENANT WS] Conversa atualizada enviada")
    
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
            logger.error(f"❌ [TENANT WS] Erro ao autenticar token: {e}")
            return None

