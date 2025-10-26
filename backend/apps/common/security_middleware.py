"""
Security middleware for sensitive operations audit
"""
import logging
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

class SecurityAuditMiddleware:
    """
    Middleware to log sensitive operations for security audit
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.sensitive_paths = [
            '/api/connections/evolution/config/',
            '/api/connections/evolution/test/',
            '/admin/',
            '/api/tenants/tenants/',  # Tenant management
            '/api/billing/',  # Billing endpoints
        ]
        
    def __call__(self, request):
        # Log sensitive endpoint access
        if any(path in request.path for path in self.sensitive_paths):
            user = request.user if not isinstance(request.user, AnonymousUser) else 'Anonymous'
            logger.warning(
                f"🔐 SENSITIVE ENDPOINT ACCESS: "
                f"Path={request.path} "
                f"Method={request.method} "
                f"User={user} "
                f"IP={self.get_client_ip(request)}"
            )
            
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Remove sensitive headers
        if 'Server' in response:
            del response['Server']
        if 'X-Powered-By' in response:
            del response['X-Powered-By']
        
        return response
        
    def get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RateLimitMiddleware:
    """
    Simple rate limiting for sensitive endpoints
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_cache = {}
        self.max_requests = 10  # Max requests
        self.time_window = 60   # Per minute
        
    def __call__(self, request):
        # Check rate limit for sensitive endpoints
        if self._is_sensitive_endpoint(request.path):
            if not self._check_rate_limit(request):
                from django.http import JsonResponse
                logger.warning(
                    f"⚠️ RATE LIMIT EXCEEDED: "
                    f"Path={request.path} "
                    f"IP={self._get_client_ip(request)}"
                )
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)
        
        response = self.get_response(request)
        return response
        
    def _is_sensitive_endpoint(self, path):
        """Check if endpoint is sensitive"""
        sensitive = [
            '/api/connections/evolution/config/',
            '/api/connections/evolution/test/',
            '/api/auth/login/',
            '/api/auth/register/',
        ]
        return any(s in path for s in sensitive)
        
    def _check_rate_limit(self, request):
        """Check if request exceeds rate limit"""
        ip = self._get_client_ip(request)
        key = f"{ip}:{request.path}"
        now = timezone.now().timestamp()
        
        # Clean old entries
        self.rate_limit_cache = {
            k: [t for t in v if now - t < self.time_window]
            for k, v in self.rate_limit_cache.items()
        }
        
        # Check current count
        if key in self.rate_limit_cache:
            if len(self.rate_limit_cache[key]) >= self.max_requests:
                return False
            self.rate_limit_cache[key].append(now)
        else:
            self.rate_limit_cache[key] = [now]
            
        return True
        
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

