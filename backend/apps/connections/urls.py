from django.urls import path
from . import views
from . import webhook_views
from . import test_views
from . import webhook_monitoring

urlpatterns = [
    # Connections list
    path('', views.ConnectionListView.as_view(), name='connection-list'),
    
    # Test endpoint
    path('test/', test_views.TestView.as_view(), name='test'),
    
    # Evolution API Configuration
    path('evolution/config/', views.evolution_config, name='evolution-config'),
    path('evolution/test/', views.test_evolution_connection, name='evolution-test'),
    
    # Webhook endpoint
    path('webhooks/evolution/', webhook_views.EvolutionWebhookView.as_view(), name='evolution-webhook'),
    
    # Webhook monitoring (admin only)
    path('webhooks/cache/stats/', webhook_monitoring.webhook_cache_stats, name='webhook-cache-stats'),
    path('webhooks/cache/events/', webhook_monitoring.webhook_recent_events, name='webhook-recent-events'),
    path('webhooks/cache/reprocess/', webhook_monitoring.webhook_reprocess_events, name='webhook-reprocess-events'),
    path('webhooks/cache/events/<str:event_id>/', webhook_monitoring.webhook_event_details, name='webhook-event-details'),
]
