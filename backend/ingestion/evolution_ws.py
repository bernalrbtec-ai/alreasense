"""
Evolution API WebSocket ingestion service.
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from django.utils import timezone
from django.conf import settings

from apps.connections.models import EvolutionConnection
from apps.chat_messages.models import Message
from apps.ai.tasks import analyze_message_async
from apps.common.utils import sanitize_pii, hash_phone_number

logger = logging.getLogger(__name__)


async def listen_connection(connection: EvolutionConnection):
    """
    Listen to Evolution API WebSocket for a specific connection.
    
    Args:
        connection: EvolutionConnection instance
    """
    
    headers = [("Authorization", f"Bearer {connection.evo_token}")]
    
    try:
        async with websockets.connect(
            connection.evo_ws_url, 
            extra_headers=headers,
            ping_interval=30,
            ping_timeout=10
        ) as websocket:
            
            logger.info(f"Connected to Evolution API for {connection.name}")
            
            async for message in websocket:
                try:
                    event = json.loads(message)
                    await handle_evolution_event(connection, event)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Evolution message: {e}")
                except Exception as e:
                    logger.error(f"Error handling Evolution event: {e}")
                    
    except websockets.exceptions.ConnectionClosed:
        logger.warning(f"Evolution WebSocket connection closed for {connection.name}")
    except Exception as e:
        logger.error(f"Failed to connect to Evolution API for {connection.name}: {e}")


async def handle_evolution_event(connection: EvolutionConnection, event: dict):
    """
    Handle incoming Evolution API event.
    
    Args:
        connection: EvolutionConnection instance
        event: Event data from Evolution API
    """
    
    event_type = event.get("type")
    
    if event_type == "message":
        await handle_message_event(connection, event)
    elif event_type == "connection.update":
        await handle_connection_update(connection, event)
    else:
        logger.debug(f"Unhandled Evolution event type: {event_type}")


async def handle_message_event(connection: EvolutionConnection, event: dict):
    """
    Handle message event from Evolution API.
    
    Args:
        connection: EvolutionConnection instance
        event: Message event data
    """
    
    try:
        # Extract message data
        chat_id = event.get("chatId")
        sender = event.get("from")
        text = event.get("body", "")
        timestamp = event.get("timestamp")
        
        if not chat_id or not sender or not text:
            logger.warning("Invalid message event: missing required fields")
            return
        
        # Sanitize PII from message text
        sanitized_text = sanitize_pii(text)
        
        # Hash sender phone number for privacy
        hashed_sender = hash_phone_number(sender)
        
        # Parse timestamp
        if timestamp:
            try:
                # Evolution API typically sends timestamp in milliseconds
                created_at = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                created_at = timezone.now()
        else:
            created_at = timezone.now()
        
        # Create message record
        message = Message.objects.create(
            tenant=connection.tenant,
            connection=connection,
            chat_id=chat_id,
            sender=hashed_sender,
            text=sanitized_text,
            created_at=created_at
        )
        
        logger.info(f"Created message {message.id} for chat {chat_id}")
        
        # Queue AI analysis
        analyze_message_async.delay(
            tenant_id=str(connection.tenant.id),
            message_id=message.id,
            is_shadow=False,
            run_id="prod"
        )
        
        # Send WebSocket notification
        await send_websocket_notification(connection.tenant.id, {
            'type': 'new_message',
            'message_id': message.id,
            'chat_id': chat_id,
            'sender': hashed_sender,
            'text_preview': sanitized_text[:100],
            'created_at': created_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to handle message event: {e}")


async def handle_connection_update(connection: EvolutionConnection, event: dict):
    """
    Handle connection status update from Evolution API.
    
    Args:
        connection: EvolutionConnection instance
        event: Connection update event data
    """
    
    try:
        status = event.get("status")
        
        if status == "connected":
            connection.is_active = True
            logger.info(f"Evolution connection {connection.name} is now active")
        elif status == "disconnected":
            connection.is_active = False
            logger.warning(f"Evolution connection {connection.name} disconnected")
        
        connection.save()
        
        # Send WebSocket notification
        await send_websocket_notification(connection.tenant.id, {
            'type': 'connection_status',
            'connection_id': connection.id,
            'connection_name': connection.name,
            'status': status,
            'is_active': connection.is_active
        })
        
    except Exception as e:
        logger.error(f"Failed to handle connection update: {e}")


async def send_websocket_notification(tenant_id: str, data: dict):
    """
    Send WebSocket notification to tenant.
    
    Args:
        tenant_id: UUID of the tenant
        data: Notification data
    """
    
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        if channel_layer:
            await channel_layer.group_send(
                f"tenant_{tenant_id}",
                {
                    "type": "broadcast_notification",
                    "payload": data
                }
            )
            
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notification: {e}")


async def start_ingestion_service():
    """
    Start the Evolution API ingestion service.
    """
    
    logger.info("Starting Evolution API ingestion service")
    
    while True:
        try:
            # Get all active connections
            connections = EvolutionConnection.objects.filter(is_active=True)
            
            if not connections:
                logger.info("No active Evolution connections found")
                await asyncio.sleep(30)  # Wait 30 seconds before checking again
                continue
            
            # Start listeners for all active connections
            tasks = [listen_connection(conn) for conn in connections]
            
            if tasks:
                logger.info(f"Starting listeners for {len(tasks)} connections")
                await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Error in ingestion service: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def run_ingestion_service():
    """
    Run the ingestion service (entry point for management command).
    """
    
    try:
        asyncio.run(start_ingestion_service())
    except KeyboardInterrupt:
        logger.info("Ingestion service stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in ingestion service: {e}")
        raise


if __name__ == "__main__":
    run_ingestion_service()
