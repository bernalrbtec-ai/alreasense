"""
Teste simples de webhook para debug
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
def simple_webhook_test(request):
    """Endpoint de teste simples para webhook"""
    try:
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0]
        
        logger.info(f"🧪 Simple webhook test - IP: {client_ip}, Method: {request.method}, Path: {request.path}")
        logger.info(f"🧪 Headers: {dict(request.headers)}")
        
        if request.method == 'POST':
            try:
                body = request.body.decode('utf-8')
                logger.info(f"🧪 POST Body: {body}")
                data = json.loads(body) if body else {}
            except:
                data = {}
        else:
            data = {}
        
        return JsonResponse({
            'status': 'success',
            'message': 'Simple webhook test working!',
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'ip': client_ip,
            'path': request.path,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"🧪 Simple webhook test error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)
