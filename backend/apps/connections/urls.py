from django.urls import path
from . import views
from . import webhook_views
from . import test_views

urlpatterns = [
    # Test endpoint
    path('test/', test_views.TestView.as_view(), name='test'),
    
    # Evolution API Configuration
    path('evolution/config/', views.evolution_config, name='evolution-config'),
    path('evolution/test/', views.test_evolution_connection, name='evolution-test'),
    
    # Webhook endpoint
    path('webhooks/evolution/', webhook_views.EvolutionWebhookView.as_view(), name='evolution-webhook'),
]
