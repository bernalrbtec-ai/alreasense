"""
URLs para Flow Chat API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.chat.api.views import (
    ConversationViewSet,
    MessageViewSet,
    MessageAttachmentViewSet
)
from apps.chat.webhooks import evolution_webhook

# Router REST
router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')

urlpatterns = [
    # REST API
    path('', include(router.urls)),
    
    # Webhook Evolution
    path('webhooks/evolution/', evolution_webhook, name='evolution-webhook'),
]

