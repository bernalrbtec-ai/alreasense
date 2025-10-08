from django.urls import path
from . import views
from . import webhook_views

urlpatterns = [
    # Evolution API Configuration
    path('evolution/config/', views.evolution_config, name='evolution-config'),
    path('evolution/test/', views.test_evolution_connection, name='evolution-test'),
    
    # Webhook endpoint
    path('webhooks/evolution/', webhook_views.EvolutionWebhookView.as_view(), name='evolution-webhook'),
]
