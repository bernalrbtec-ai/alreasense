from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationTemplateViewSet,
    WhatsAppInstanceViewSet,
    NotificationLogViewSet
)

router = DefaultRouter()
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'whatsapp-instances', WhatsAppInstanceViewSet, basename='whatsapp-instance')
router.register(r'logs', NotificationLogViewSet, basename='notification-log')

urlpatterns = [
    path('', include(router.urls)),
]

