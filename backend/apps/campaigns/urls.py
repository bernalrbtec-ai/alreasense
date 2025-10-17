from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, CampaignNotificationViewSet
from .views_v2 import (
    CampaignControlView, campaign_health, system_health, 
    active_campaigns, resolve_alert, campaign_metrics
)
from .views_realtime import campaign_realtime_status, campaign_realtime_progress
from .views_events import campaign_events, campaign_realtime_status as campaign_events_status
from .views_events_debug import campaign_events_debug
from .views_status import campaign_status
from .views_logs import campaign_logs as campaign_logs_new, campaign_logs_stats
from .views_retry import campaign_retry_info
from .views_debug import debug_campaigns, test_retry_endpoint
from .views_debug_campaign import debug_campaign_state
from .views_test_presence import test_send_presence, list_instances_for_test
# CampaignNotificationViewSet reativado

router = DefaultRouter()
router.register(r'', CampaignViewSet, basename='campaign')
router.register(r'notifications', CampaignNotificationViewSet, basename='notification')

urlpatterns = [
    # APIs de status simples - DEVE VIR ANTES DO ROUTER
    path('campaigns/status/', campaign_status, name='campaign-status'),
    
    # APIs de eventos para contador real - DEVE VIR ANTES DO ROUTER
    path('campaigns/events/', campaign_events, name='campaign-events'),
    path('campaigns/events-debug/', campaign_events_debug, name='campaign-events-debug'),
    path('campaigns/<uuid:campaign_id>/events-status/', campaign_events_status, name='campaign-events-status'),
    
    # APIs de logs de campanhas
    path('campaigns/logs/', campaign_logs_new, name='campaign-logs'),
    path('campaigns/logs/stats/', campaign_logs_stats, name='campaign-logs-stats'),
    
    # API de informações de retry
    path('campaigns/<uuid:campaign_id>/retry-info/', campaign_retry_info, name='campaign-retry-info'),
    
    # API de debug para campanhas
    path('campaigns/debug/', debug_campaigns, name='campaigns-debug'),
    path('campaigns/<uuid:campaign_id>/test-retry/', test_retry_endpoint, name='test-retry-endpoint'),
    path('campaigns/<uuid:campaign_id>/debug/', debug_campaign_state, name='debug-campaign-state'),
    
    # API de teste de presença (digitando)
    path('campaigns/test-presence/', test_send_presence, name='test-presence'),
    path('campaigns/test-presence/instances/', list_instances_for_test, name='test-presence-instances'),
    
    # Router deve vir depois das URLs específicas
    path('', include(router.urls)),
    
    # V2 - Sistema com RabbitMQ
    path('v2/campaigns/<uuid:campaign_id>/<str:action>/', CampaignControlView.as_view(), name='campaign-control'),
    path('v2/campaigns/<uuid:campaign_id>/health/', campaign_health, name='campaign-health'),
    path('v2/campaigns/<uuid:campaign_id>/metrics/', campaign_metrics, name='campaign-metrics'),
    path('v2/campaigns/<uuid:campaign_id>/alerts/<str:alert_id>/resolve/', resolve_alert, name='resolve-alert'),
    path('v2/campaigns/active/', active_campaigns, name='active-campaigns'),
    path('v2/system/health/', system_health, name='system-health'),
    
    # APIs de status em tempo real
    path('campaigns/<uuid:campaign_id>/realtime/', campaign_realtime_status, name='campaign-realtime'),
    path('campaigns/<uuid:campaign_id>/progress/', campaign_realtime_progress, name='campaign-progress'),
]




