from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationTemplateViewSet,
    WhatsAppInstanceViewSet,
    NotificationLogViewSet,
    SMTPConfigViewSet,
    UserNotificationPreferencesViewSet,
    DepartmentNotificationPreferencesViewSet
)

router = DefaultRouter()
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'whatsapp-instances', WhatsAppInstanceViewSet, basename='whatsapp-instance')
router.register(r'smtp-configs', SMTPConfigViewSet, basename='smtp-config')
router.register(r'logs', NotificationLogViewSet, basename='notification-log')
# Sistema de Notificações Personalizadas
router.register(r'user-preferences', UserNotificationPreferencesViewSet, basename='user-notification-preferences')
router.register(r'department-preferences', DepartmentNotificationPreferencesViewSet, basename='department-notification-preferences')

urlpatterns = [
    path('', include(router.urls)),
]

