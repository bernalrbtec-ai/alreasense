"""
URLs para Flow Chat API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.chat.api.views import (
    ConversationViewSet,
    MessageViewSet,
    MessageAttachmentViewSet,
    MessageReactionViewSet
)
from apps.chat.views import media_proxy
from apps.chat.webhooks import evolution_webhook
from apps.chat.api.media_views import serve_media

# Router REST
router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')
router.register(r'reactions', MessageReactionViewSet, basename='reaction')

urlpatterns = [
    # REST API
    path('', include(router.urls)),
    
    # 🔗 Serve mídia com cache Redis (7 dias) + S3 (30 dias)
    # URL curta para Evolution API: /media/{hash}
    path('media/<str:media_hash>/', serve_media, name='serve-media'),
    # Compatibilidade: aceitar sem barra final (short_url antiga)
    path('media/<str:media_hash>', serve_media),
    
    # Proxy universal de mídia (público - sem autenticação)
    path('media-proxy/', media_proxy, name='media-proxy'),
    # Alias para compatibilidade
    path('profile-pic-proxy/', media_proxy, name='profile-pic-proxy'),
    
    # Webhook Evolution
    path('webhooks/evolution/', evolution_webhook, name='evolution-webhook'),
]
