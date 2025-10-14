"""
Celery tasks for experiments app.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta

from .models import PromptTemplate, Inference
from apps.chat_messages.models import Message
# ✅ IMPORT MOVIDO PARA DENTRO DA FUNÇÃO para evitar loop circular

logger = logging.getLogger(__name__)


@shared_task
def replay_window(tenant_id: str, start_date: str, end_date: str, prompt_template_id: str):
    """
    Replay messages in a time window with a specific prompt template.
    """
    try:
        tenant_id = str(tenant_id)
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Get the prompt template
        prompt_template = PromptTemplate.objects.get(
            id=prompt_template_id,
            tenant_id=tenant_id
        )
        
        # Get messages in the time window
        messages = Message.objects.filter(
            tenant_id=tenant_id,
            created_at__range=[start_date, end_date]
        ).order_by('created_at')
        
        total_messages = messages.count()
        processed = 0
        
        logger.info(f"Starting replay for {total_messages} messages with template {prompt_template_id}")
        
        for message in messages:
            # Create inference record
            inference = Inference.objects.create(
                tenant_id=tenant_id,
                message=message,
                prompt_template=prompt_template,
                status='running'
            )
            
            # ✅ Enqueue AI analysis with the specific prompt template (IMPORT LOCAL)
            from apps.ai.tasks import analyze_message_async
            analyze_message_async.delay(
                tenant_id=tenant_id,
                message_id=str(message.id),
                prompt_template_id=prompt_template_id,
                inference_id=str(inference.id)
            )
            
            processed += 1
            
            if processed % 100 == 0:
                logger.info(f"Processed {processed}/{total_messages} messages")
        
        logger.info(f"Replay completed: {processed} messages processed")
        return {
            'status': 'completed',
            'total_messages': total_messages,
            'processed': processed
        }
        
    except Exception as e:
        logger.error(f"Error in replay_window task: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
