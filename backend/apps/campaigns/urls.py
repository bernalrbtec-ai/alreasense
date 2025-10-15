from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, CampaignNotificationViewSet
from .views_v2 import (
    CampaignControlView, campaign_health, system_health, 
    active_campaigns, resolve_alert, campaign_metrics
)
from .views_realtime import campaign_realtime_status, campaign_realtime_progress
# CampaignNotificationViewSet reativado

router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'notifications', CampaignNotificationViewSet, basename='notification')

urlpatterns = [
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




