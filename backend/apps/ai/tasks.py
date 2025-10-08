"""
Celery tasks for AI analysis.
"""

import time
import requests
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.chat_messages.models import Message
from apps.chat_messages.dao import write_embedding
from apps.experiments.models import Inference, PromptTemplate
from .embeddings import embed_text

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_message_async(
    self, 
    tenant_id: str, 
    message_id: int, 
    prompt_version: str = None, 
    is_shadow: bool = False, 
    run_id: str = "prod"
):
    """
    Analyze a message using AI.
    
    Args:
        tenant_id: UUID of the tenant
        message_id: ID of the message to analyze
        prompt_version: Version of prompt to use
        is_shadow: Whether this is a shadow inference
        run_id: Experiment run ID
    """
    
    try:
        # Get message
        message = Message.objects.get(id=message_id)
        
        # Get prompt template
        if prompt_version:
            template = PromptTemplate.objects.get(version=prompt_version)
        else:
            template = PromptTemplate.objects.order_by('-created_at').first()
        
        if not template:
            logger.error(f"No prompt template found for message {message_id}")
            return
        
        # Prepare payload for AI service
        payload = {
            "tenant_id": tenant_id,
            "message": message.text,
            "context": {
                "chat_id": message.chat_id,
                "sender": message.sender,
                "created_at": message.created_at.isoformat()
            },
            "prompt_version": template.version,
            "is_shadow": is_shadow,
            "run_id": run_id
        }
        
        # Call AI service
        start_time = time.time()
        
        if settings.N8N_AI_WEBHOOK:
            response = requests.post(
                settings.N8N_AI_WEBHOOK,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            ai_result = response.json()
        else:
            # Fallback to mock analysis
            ai_result = _mock_ai_analysis(message.text)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Parse AI results
        sentiment = ai_result.get('sentiment', 0.0)
        emotion = ai_result.get('emotion', 'neutral')
        satisfaction = ai_result.get('satisfaction', 50)
        tone = ai_result.get('tone', 'neutral')
        summary = ai_result.get('summary', '')
        model_name = ai_result.get('model', settings.AI_MODEL_NAME)
        
        # Update message (only for champion, not shadow)
        if not is_shadow:
            message.sentiment = sentiment
            message.emotion = emotion
            message.satisfaction = satisfaction
            message.tone = tone
            message.summary = summary
            message.save(update_fields=[
                'sentiment', 'emotion', 'satisfaction', 'tone', 'summary'
            ])
        
        # Generate and store embedding
        try:
            embedding = embed_text(message.text)
            if embedding:
                write_embedding(message.id, embedding)
        except Exception as e:
            logger.warning(f"Failed to generate embedding for message {message_id}: {e}")
        
        # Store inference record
        Inference.objects.create(
            tenant_id=tenant_id,
            message=message,
            model_name=model_name,
            prompt_version=template.version,
            template_hash=hash(template.body),
            latency_ms=latency_ms,
            sentiment=sentiment,
            emotion=emotion,
            satisfaction=satisfaction,
            is_shadow=is_shadow,
            run_id=run_id
        )
        
        # Send WebSocket notification
        if not is_shadow:
            _send_websocket_notification(tenant_id, {
                'message_id': message.id,
                'sentiment': sentiment,
                'emotion': emotion,
                'satisfaction': satisfaction,
                'tone': tone,
                'summary': summary,
                'latency_ms': latency_ms
            })
        
        logger.info(f"Analyzed message {message_id} in {latency_ms}ms")
        
    except Message.DoesNotExist:
        logger.error(f"Message {message_id} not found")
    except PromptTemplate.DoesNotExist:
        logger.error(f"Prompt template {prompt_version} not found")
    except Exception as e:
        logger.error(f"Failed to analyze message {message_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))


@shared_task
def replay_window(
    tenant_id: str, 
    start_iso: str, 
    end_iso: str, 
    prompt_version: str, 
    run_id: str
):
    """
    Replay analysis for a time window with a specific prompt version.
    
    Args:
        tenant_id: UUID of the tenant
        start_iso: Start date in ISO format
        end_iso: End date in ISO format
        prompt_version: Version of prompt to use
        run_id: Experiment run ID
    """
    
    from datetime import datetime
    
    start_date = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
    
    # Get messages in time window
    message_ids = Message.objects.filter(
        tenant_id=tenant_id,
        created_at__range=[start_date, end_date]
    ).values_list('id', flat=True)
    
    # Queue analysis tasks
    for message_id in message_ids:
        analyze_message_async.delay(
            tenant_id=tenant_id,
            message_id=message_id,
            prompt_version=prompt_version,
            is_shadow=True,
            run_id=run_id
        )
    
    logger.info(f"Queued {len(message_ids)} messages for replay with prompt {prompt_version}")


def _mock_ai_analysis(text: str) -> dict:
    """Mock AI analysis for testing."""
    
    # Simple sentiment analysis based on keywords
    positive_words = ['bom', 'ótimo', 'excelente', 'satisfeito', 'feliz', 'obrigado']
    negative_words = ['ruim', 'péssimo', 'insatisfeito', 'problema', 'erro', 'reclamação']
    
    text_lower = text.lower()
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        sentiment = 0.7
        emotion = 'positivo'
        satisfaction = 85
        tone = 'cordial'
    elif negative_count > positive_count:
        sentiment = -0.6
        emotion = 'negativo'
        satisfaction = 25
        tone = 'frustrado'
    else:
        sentiment = 0.0
        emotion = 'neutro'
        satisfaction = 50
        tone = 'neutro'
    
    return {
        'sentiment': sentiment,
        'emotion': emotion,
        'satisfaction': satisfaction,
        'tone': tone,
        'summary': f'Análise automática: {emotion}',
        'model': 'mock-model'
    }


def _send_websocket_notification(tenant_id: str, data: dict):
    """Send WebSocket notification to tenant."""
    
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"tenant_{tenant_id}",
            {
                "type": "message_analyzed",
                "payload": data
            }
        )
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notification: {e}")
