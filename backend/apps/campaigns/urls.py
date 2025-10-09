from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.campaigns.views import (
    CampaignViewSet, CampaignMessageViewSet, HolidayViewSet
)

router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'holidays', HolidayViewSet, basename='holiday')

urlpatterns = [
    path('', include(router.urls)),
    # Mensagens de campanha via nested URL
    path('campaigns/<uuid:campaign_pk>/messages/', 
         CampaignMessageViewSet.as_view({'get': 'list', 'post': 'create'}), 
         name='campaign-messages-list'),
    path('campaigns/<uuid:campaign_pk>/messages/<uuid:pk>/', 
         CampaignMessageViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), 
         name='campaign-messages-detail'),
    path('campaigns/<uuid:campaign_pk>/messages/<uuid:pk>/preview/', 
         CampaignMessageViewSet.as_view({'get': 'preview'}), 
         name='campaign-messages-preview'),
]

