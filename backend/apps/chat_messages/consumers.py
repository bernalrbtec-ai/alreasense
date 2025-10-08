import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from apps.authn.models import User


class TenantConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for tenant-specific real-time updates."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group_name = f"tenant_{self.tenant_id}"
        
        # Add to tenant group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connection_established',
            'tenant_id': self.tenant_id,
            'message': 'Connected to tenant updates'
        })
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get('type')
        
        if message_type == 'ping':
            await self.send_json({'type': 'pong'})
        elif message_type == 'subscribe_chat':
            chat_id = content.get('chat_id')
            if chat_id:
                chat_group = f"chat_{self.tenant_id}_{chat_id}"
                await self.channel_layer.group_add(
                    chat_group,
                    self.channel_name
                )
                await self.send_json({
                    'type': 'subscribed',
                    'chat_id': chat_id
                })
        elif message_type == 'unsubscribe_chat':
            chat_id = content.get('chat_id')
            if chat_id:
                chat_group = f"chat_{self.tenant_id}_{chat_id}"
                await self.channel_layer.group_discard(
                    chat_group,
                    self.channel_name
                )
                await self.send_json({
                    'type': 'unsubscribed',
                    'chat_id': chat_id
                })
    
    # Event handlers for group messages
    async def message_analyzed(self, event):
        """Handle message analysis completion."""
        await self.send_json({
            'type': 'message_analyzed',
            'data': event['payload']
        })
    
    async def new_message(self, event):
        """Handle new message received."""
        await self.send_json({
            'type': 'new_message',
            'data': event['payload']
        })
    
    async def connection_status(self, event):
        """Handle connection status updates."""
        await self.send_json({
            'type': 'connection_status',
            'data': event['payload']
        })
    
    async def experiment_result(self, event):
        """Handle experiment results."""
        await self.send_json({
            'type': 'experiment_result',
            'data': event['payload']
        })
    
    async def billing_update(self, event):
        """Handle billing updates."""
        await self.send_json({
            'type': 'billing_update',
            'data': event['payload']
        })
