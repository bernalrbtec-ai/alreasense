"""
URL configuration for alrea_sense project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    """Health check endpoint."""
    return JsonResponse({"status": "healthy", "service": "alrea_sense"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),
    path('api/auth/', include('apps.authn.urls')),
    path('api/tenants/', include('apps.tenancy.urls')),
    path('api/messages/', include('apps.chat_messages.urls')),
    path('api/connections/', include('apps.connections.urls')),
    path('api/ai/', include('apps.ai.urls')),
    path('api/experiments/', include('apps.experiments.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/webhooks/', include('apps.billing.webhook_urls')),
    path('api/webhooks/evolution/', include('apps.connections.urls')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
