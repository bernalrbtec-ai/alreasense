"""
Middleware para debug detalhado de webhooks
"""

import logging
import json
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class WebhookDebugMiddleware(MiddlewareMixin):
    """
    Middleware para debug detalhado de requests webhook
    """
    
    def process_request(self, request):
        """Log detalhado de cada request para webhook"""
        if request.path.startswith('/webhooks/'):
            logger.info(f"🔍 WEBHOOK DEBUG - REQUEST START")
            logger.info(f"🔍 Path: {request.path}")
            logger.info(f"🔍 Method: {request.method}")
            logger.info(f"🔍 Remote IP: {request.META.get('REMOTE_ADDR')}")
            logger.info(f"🔍 X-Forwarded-For: {request.META.get('HTTP_X_FORWARDED_FOR')}")
            logger.info(f"🔍 User-Agent: {request.META.get('HTTP_USER_AGENT')}")
            logger.info(f"🔍 Content-Type: {request.META.get('CONTENT_TYPE')}")
            logger.info(f"🔍 Content-Length: {request.META.get('CONTENT_LENGTH')}")
            logger.info(f"🔍 Host: {request.META.get('HTTP_HOST')}")
            logger.info(f"🔍 Headers: {dict(request.headers)}")
            
            # Log do body se for POST
            if request.method == 'POST' and request.body:
                try:
                    body_str = request.body.decode('utf-8')
                    logger.info(f"🔍 Body: {body_str}")
                    try:
                        body_json = json.loads(body_str)
                        logger.info(f"🔍 Body JSON: {json.dumps(body_json, indent=2)}")
                    except:
                        logger.info(f"🔍 Body (not JSON): {body_str}")
                except Exception as e:
                    logger.error(f"🔍 Error decoding body: {str(e)}")
            
            logger.info(f"🔍 WEBHOOK DEBUG - REQUEST INFO COMPLETE")
    
    def process_response(self, request, response):
        """Log detalhado da resposta para webhook"""
        if request.path.startswith('/webhooks/'):
            logger.info(f"🔍 WEBHOOK DEBUG - RESPONSE")
            logger.info(f"🔍 Status Code: {response.status_code}")
            logger.info(f"🔍 Content Type: {response.get('Content-Type')}")
            logger.info(f"🔍 Headers: {dict(response.headers)}")
            
            # Log do conteúdo da resposta se for erro
            if response.status_code >= 400:
                try:
                    if hasattr(response, 'content'):
                        content = response.content.decode('utf-8')
                        logger.info(f"🔍 Response Content: {content}")
                except Exception as e:
                    logger.error(f"🔍 Error reading response content: {str(e)}")
            
            logger.info(f"🔍 WEBHOOK DEBUG - RESPONSE COMPLETE")
        
        return response
    
    def process_exception(self, request, exception):
        """Log detalhado de exceções para webhook"""
        if request.path.startswith('/webhooks/'):
            logger.error(f"🔍 WEBHOOK DEBUG - EXCEPTION")
            logger.error(f"🔍 Exception Type: {type(exception).__name__}")
            logger.error(f"🔍 Exception Message: {str(exception)}")
            logger.error(f"🔍 Exception Args: {exception.args}")
            
            import traceback
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
            
            logger.error(f"🔍 WEBHOOK DEBUG - EXCEPTION COMPLETE")
        
        return None
