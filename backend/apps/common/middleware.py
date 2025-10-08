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
    """
    
    def process_request(self, request):
        """Add tenant context to request."""
        
        # Add request ID for tracking
        request.request_id = str(uuid.uuid4())[:8]
        
        # Add tenant context if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.tenant = request.user.tenant
            request.tenant_id = str(request.user.tenant.id)
        else:
            request.tenant = None
            request.tenant_id = None
        
        # Log request with context
        logger.info(
            f"Request {request.request_id} - "
            f"User: {getattr(request.user, 'username', 'anonymous')} - "
            f"Tenant: {getattr(request.tenant, 'name', 'none')} - "
            f"Path: {request.path}"
        )
    
    def process_response(self, request, response):
        """Add request ID to response headers."""
        
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        return response
