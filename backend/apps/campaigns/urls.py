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
from .views_pdf import export_campaign_pdf
from .views_debug import debug_campaigns, test_retry_endpoint
from .views_debug_campaign import debug_campaign_state
from .views_test_presence import test_send_presence, list_instances_for_test
# CampaignNotificationViewSet reativado

router = DefaultRouter()
router.register(r'', CampaignViewSet, basename='campaign')
router.register(r'notifications', CampaignNotificationViewSet, basename='notification')

urlpatterns = [
    # APIs de logs de campanhas - DEVE VIR ANTES DE TUDO
    path('logs/', campaign_logs_new, name='campaign-logs'),
    path('logs/stats/', campaign_logs_stats, name='campaign-logs-stats'),
    
    # APIs de status simples - DEVE VIR ANTES DO ROUTER
    path('status/', campaign_status, name='campaign-status'),
    
    # APIs de eventos para contador real - DEVE VIR ANTES DO ROUTER
    path('events/', campaign_events, name='campaign-events'),
    path('events-debug/', campaign_events_debug, name='campaign-events-debug'),
    path('<uuid:campaign_id>/events-status/', campaign_events_status, name='campaign-events-status'),
    
    # API de informações de retry
    path('<uuid:campaign_id>/retry-info/', campaign_retry_info, name='campaign-retry-info'),
    
    # API de exportação de PDF
    path('<uuid:campaign_id>/export-pdf/', export_campaign_pdf, name='campaign-export-pdf'),
    
    # API de debug para campanhas
    path('debug/', debug_campaigns, name='campaigns-debug'),
    path('<uuid:campaign_id>/test-retry/', test_retry_endpoint, name='test-retry-endpoint'),
    path('<uuid:campaign_id>/debug/', debug_campaign_state, name='debug-campaign-state'),
    
    # API de teste de presença (digitando)
    path('test-presence/', test_send_presence, name='test-presence'),
    path('test-presence/instances/', list_instances_for_test, name='test-presence-instances'),
    
    # Router deve vir depois das URLs específicas
    path('', include(router.urls)),
    
    # V2 - Sistema com RabbitMQ
    path('v2/<uuid:campaign_id>/<str:action>/', CampaignControlView.as_view(), name='campaign-control'),
    path('v2/<uuid:campaign_id>/health/', campaign_health, name='campaign-health'),
    path('v2/<uuid:campaign_id>/metrics/', campaign_metrics, name='campaign-metrics'),
    path('v2/<uuid:campaign_id>/alerts/<str:alert_id>/resolve/', resolve_alert, name='resolve-alert'),
    path('v2/active/', active_campaigns, name='active-campaigns'),
    path('v2/system/health/', system_health, name='system-health'),
    
    # APIs de status em tempo real
    path('<uuid:campaign_id>/realtime/', campaign_realtime_status, name='campaign-realtime'),
    path('<uuid:campaign_id>/progress/', campaign_realtime_progress, name='campaign-progress'),
]




