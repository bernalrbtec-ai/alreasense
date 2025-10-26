"""
Performance monitoring middleware.
Tracks slow requests and adds response time headers.
"""
import time
import logging
from django.conf import settings

logger = logging.getLogger('performance')


class PerformanceMiddleware:
    """
    Middleware para monitorar performance de requests.
    
    Features:
    - Adiciona header X-Response-Time em todas as respostas
    - Loga requests lentos (> 1 segundo)
    - Captura métricas para análise
    """
    
    # Threshold em segundos para considerar request "lento"
    SLOW_REQUEST_THRESHOLD = 1.0
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Ignorar requests de healthcheck e static files
        if self._should_skip(request.path):
            return self.get_response(request)
        
        start_time = time.time()
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Add response time header (sempre)
        response['X-Response-Time'] = f"{duration:.3f}s"
        
        # Log slow requests
        if duration > self.SLOW_REQUEST_THRESHOLD:
            self._log_slow_request(request, response, duration)
        
        return response
    
    def _should_skip(self, path):
        """Determina se o path deve ser ignorado."""
        skip_paths = [
            '/api/health/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]
        return any(path.startswith(skip) for skip in skip_paths)
    
    def _log_slow_request(self, request, response, duration):
        """Loga informações sobre requests lentos."""
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
        tenant_id = getattr(request.user, 'tenant_id', None) if hasattr(request, 'user') else None
        
        logger.warning(
            f"⏱️ SLOW REQUEST: {request.method} {request.path}",
            extra={
                'duration': round(duration, 3),
                'status_code': response.status_code,
                'user_id': user_id,
                'tenant_id': str(tenant_id) if tenant_id else None,
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET),
            }
        )


class DatabaseQueryCountMiddleware:
    """
    Middleware para contar queries de banco de dados em desenvolvimento.
    Apenas ativo quando DEBUG=True.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Apenas em DEBUG mode
        if not settings.DEBUG:
            return self.get_response(request)
        
        from django.db import connection, reset_queries
        
        # Reset query log
        reset_queries()
        
        # Process request
        response = self.get_response(request)
        
        # Get query count
        query_count = len(connection.queries)
        
        # Add header
        response['X-DB-Query-Count'] = str(query_count)
        
        # Log if too many queries
        if query_count > 50:
            logger.warning(
                f"🔍 HIGH QUERY COUNT: {request.path}",
                extra={
                    'query_count': query_count,
                    'path': request.path,
                }
            )
        
        return response

