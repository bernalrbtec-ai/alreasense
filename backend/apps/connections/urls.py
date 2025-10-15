from django.urls import path
from . import views
from . import webhook_views
from . import test_views
from . import webhook_monitoring_views
from . import test_webhook_endpoint
from . import simple_webhook_test
from . import simple_webhook_view
from . import super_simple_webhook
from . import views_mongodb

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
    
    # Simple webhook test
    path('webhooks/test-simple/', simple_webhook_test.simple_webhook_test, name='simple-webhook-test'),
    
    # Simple Evolution webhook
    path('webhooks/evolution-simple/', simple_webhook_view.simple_webhook_evolution, name='evolution-webhook-simple'),
    
    # Super Simple webhook (NO VALIDATION)
    path('webhooks/super-simple/', super_simple_webhook.super_simple_webhook, name='super-simple-webhook'),
    
    # Webhook test endpoint (admin only)
    path('webhooks/test/', test_webhook_endpoint.TestWebhookEndpointView.as_view(), name='webhook-test'),
    
    # Webhook monitoring (admin only)
    path('webhooks/cache/stats/', webhook_monitoring_views.WebhookCacheStatsView.as_view(), name='webhook-cache-stats'),
    path('webhooks/cache/events/', webhook_monitoring_views.WebhookCacheEventsView.as_view(), name='webhook-recent-events'),
    path('webhooks/cache/reprocess/', webhook_monitoring_views.WebhookCacheReprocessView.as_view(), name='webhook-reprocess-events'),
    path('webhooks/cache/events/<str:event_id>/', webhook_monitoring_views.WebhookCacheEventDetailView.as_view(), name='webhook-event-details'),
    
    # MongoDB webhook events
    path('webhooks/mongodb/stats/', views_mongodb.webhook_events_stats, name='webhook-mongodb-stats'),
    path('webhooks/mongodb/events/', views_mongodb.webhook_events_list, name='webhook-mongodb-events'),
    path('webhooks/mongodb/reprocess/', views_mongodb.reprocess_webhook_event, name='webhook-mongodb-reprocess'),
]
