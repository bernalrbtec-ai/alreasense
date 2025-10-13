"""
Super simple webhook endpoint - NO VALIDATION AT ALL
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST", "GET"])
def super_simple_webhook(request):
    """Super simple webhook with ZERO validation."""
    try:
        logger.info(f"🎯 SUPER SIMPLE WEBHOOK - Method: {request.method}")
        logger.info(f"🎯 SUPER SIMPLE WEBHOOK - Path: {request.path}")
        logger.info(f"🎯 SUPER SIMPLE WEBHOOK - IP: {request.META.get('REMOTE_ADDR')}")
        
        if request.method == 'GET':
            logger.info(f"🎯 SUPER SIMPLE WEBHOOK - GET request received!")
            return JsonResponse({
                'status': 'success',
                'message': 'Super simple webhook is working!',
                'method': 'GET'
            })
        
        elif request.method == 'POST':
            logger.info(f"🎯 SUPER SIMPLE WEBHOOK - POST request received!")
            
            # Try to parse JSON
            try:
                data = json.loads(request.body)
                logger.info(f"🎯 SUPER SIMPLE WEBHOOK - JSON data: {json.dumps(data, indent=2)}")
            except Exception as e:
                logger.info(f"🎯 SUPER SIMPLE WEBHOOK - Raw body: {request.body}")
                data = {'raw_body': str(request.body)}
            
            return JsonResponse({
                'status': 'success',
                'message': 'Super simple webhook received data!',
                'method': 'POST',
                'data': data
            })
    
    except Exception as e:
        logger.error(f"🎯 SUPER SIMPLE WEBHOOK ERROR: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
