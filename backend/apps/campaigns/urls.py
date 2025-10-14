from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet
# CampaignNotificationViewSet temporariamente comentado

router = DefaultRouter()
router.register(r'campaigns', CampaignViewSet, basename='campaign')
# router.register(r'notifications', CampaignNotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]




