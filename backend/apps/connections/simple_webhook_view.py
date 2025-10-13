"""
View webhook simples para debug
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def simple_webhook_evolution(request):
    """Webhook Evolution simples para debug"""
    try:
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0]
        
        logger.info(f"🚀 Simple Evolution Webhook - IP: {client_ip}, Method: {request.method}")
        logger.info(f"🚀 Headers: {dict(request.headers)}")
        
        if request.method == 'POST':
            try:
                body = request.body.decode('utf-8')
                logger.info(f"🚀 POST Body: {body}")
                data = json.loads(body) if body else {}
                
                # Simular processamento
                event_type = data.get('event', 'unknown')
                logger.info(f"🚀 Event type: {event_type}")
                
            except Exception as e:
                logger.error(f"🚀 Error parsing body: {str(e)}")
                data = {}
        else:
            data = {}
        
        return JsonResponse({
            'status': 'success',
            'message': 'Simple Evolution webhook working!',
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'ip': client_ip,
            'event': data.get('event', 'none'),
            'data_received': len(str(data))
        })
        
    except Exception as e:
        logger.error(f"🚀 Simple Evolution webhook error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)
