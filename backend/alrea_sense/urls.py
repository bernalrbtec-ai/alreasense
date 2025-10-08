"""
URL configuration for alrea_sense project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.common.health import get_system_health

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Comprehensive health check endpoint."""
    health_data = get_system_health()
    status_code = 200 if health_data['status'] in ['healthy', 'degraded'] else 503
    
    response = JsonResponse(health_data, status=status_code)
    # Add CORS headers explicitly
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health'),
    path('api/auth/', include('apps.authn.urls')),
    path('api/tenants/', include('apps.tenancy.urls')),
    path('api/messages/', include('apps.chat_messages.urls')),
    path('api/connections/', include('apps.connections.urls')),
    path('api/ai/', include('apps.ai.urls')),
    path('api/experiments/', include('apps.experiments.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/webhooks/', include('apps.billing.webhook_urls')),
    path('api/webhooks/evolution/', include('apps.connections.urls')),
]

# Serve static and media files
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
