"""
Custom middleware for tenant isolation and request tracking.
"""

import uuid
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to add tenant context to requests.
    
    IMPORTANTE: Este middleware deve vir DEPOIS do AuthenticationMiddleware
    mas a autenticação JWT do DRF acontece na view, não no middleware.
    Por isso, vamos usar process_view para ter acesso ao usuário autenticado.
    """
    
    def process_request(self, request):
        """Add request ID to request."""
        # Add request ID for tracking
        request.request_id = str(uuid.uuid4())[:8]
        
        # Skip tenant processing for webhooks (they don't need authentication)
        if request.path.startswith('/webhooks/'):
            request.tenant = None
            request.tenant_id = None
            return None  # Skip further processing
        
        # Inicializar tenant como None (será preenchido no process_view)
        request.tenant = None
        request.tenant_id = None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Add tenant context to request after authentication.
        Este método é chamado DEPOIS da autenticação do DRF.
        """
        # Skip tenant processing for webhooks (they don't need authentication)
        if request.path.startswith('/webhooks/'):
            logger.info(f"Request {request.request_id} - Webhook: {request.path}")
            return None
        
        # Add tenant context if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.tenant = getattr(request.user, 'tenant', None)
            request.tenant_id = str(request.tenant.id) if request.tenant else None
        else:
            # Se não há usuário autenticado, tentar obter do token JWT manualmente
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                jwt_auth = JWTAuthentication()
                auth_result = jwt_auth.authenticate(request)
                if auth_result:
                    user, token = auth_result
                    request.user = user
                    request.tenant = getattr(user, 'tenant', None)
                    request.tenant_id = str(request.tenant.id) if request.tenant else None
            except Exception as e:
                # Se falhar, continuar sem tenant
                pass
        
        # Log request with context - só logar se não for webhook
        if not request.path.startswith('/webhooks/'):
            user_info = 'anonymous'
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_info = getattr(request.user, 'email', getattr(request.user, 'username', 'authenticated'))
            
            tenant_info = 'none'
            if hasattr(request, 'tenant') and request.tenant:
                tenant_info = getattr(request.tenant, 'name', 'unknown')
            
            logger.info(
                f"Request {request.request_id} - "
                f"User: {user_info} - "
                f"Tenant: {tenant_info} - "
                f"Path: {request.path}"
            )
    
    def process_response(self, request, response):
        """Add request ID to response headers."""
        
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        return response
    
    def process_exception(self, request, exception):
        """Handle exceptions in webhook requests."""
        if request.path.startswith('/webhooks/'):
            logger.error(f"Webhook exception: {str(exception)}")
            return None
        return None
