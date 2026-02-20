"""
URLs para Flow Chat API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.chat.api.views import (
    ConversationViewSet,
    MessageViewSet,
    MessageAttachmentViewSet,
    MessageReactionViewSet,
    chat_metrics_overview,
    chat_ping_evolution,
    chat_diagnose_instance_friendly_name,
    UploadPresignedUrlView,
    ConfirmUploadView,
    ConfirmUploadBatchView,
)
from apps.chat.api.views_metrics import message_metrics, message_metrics_rebuild
from apps.chat.api.views_reports_sync import reports_sync_incremental
from apps.chat.api.views_business_hours import (
    BusinessHoursViewSet,
    AfterHoursMessageViewSet,
    AfterHoursTaskConfigViewSet,
)
from apps.chat.api.views_welcome_menu import WelcomeMenuConfigViewSet
from apps.chat.api.views_quick_replies import QuickReplyViewSet
from apps.chat.views import media_proxy
from apps.chat.webhooks import evolution_webhook
from apps.chat.api.media_views import serve_media

# Router REST
router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', MessageAttachmentViewSet, basename='attachment')
router.register(r'reactions', MessageReactionViewSet, basename='reaction')
router.register(r'business-hours', BusinessHoursViewSet, basename='business-hours')
router.register(r'after-hours-messages', AfterHoursMessageViewSet, basename='after-hours-message')
router.register(r'after-hours-task-configs', AfterHoursTaskConfigViewSet, basename='after-hours-task-config')
router.register(r'welcome-menu-config', WelcomeMenuConfigViewSet, basename='welcome-menu-config')
router.register(r'quick-replies', QuickReplyViewSet, basename='quick-reply')

urlpatterns = [
    # ✅ FIX: Rotas customizadas (URLs diferentes para evitar conflito com router)
    path('upload-presigned-url/', UploadPresignedUrlView.as_view(), name='message-upload-presigned-url'),
    path('upload-presigned-url', UploadPresignedUrlView.as_view(), name='message-upload-presigned-url-no-slash'),
    path('confirm-upload/', ConfirmUploadView.as_view(), name='message-confirm-upload'),
    path('confirm-upload', ConfirmUploadView.as_view(), name='message-confirm-upload-no-slash'),
    path('confirm-upload-batch/', ConfirmUploadBatchView.as_view(), name='message-confirm-upload-batch'),
    path('confirm-upload-batch', ConfirmUploadBatchView.as_view(), name='message-confirm-upload-batch-no-slash'),
    
    # REST API (router deve vir depois das rotas customizadas)
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
    # Monitores/diagnósticos
    path('metrics/overview/', chat_metrics_overview, name='chat-metrics-overview'),
    path('metrics/messages/', message_metrics, name='chat-metrics-messages'),
    path('metrics/messages/rebuild/', message_metrics_rebuild, name='chat-metrics-messages-rebuild'),
    path('reports/sync/incremental/', reports_sync_incremental, name='reports-sync-incremental'),
    path('reports/sync/incremental', reports_sync_incremental, name='reports-sync-incremental-no-slash'),
    path('metrics/ping-evolution/', chat_ping_evolution, name='chat-ping-evolution'),
    path('metrics/diagnose-instance-friendly-name/', chat_diagnose_instance_friendly_name, name='chat-diagnose-instance-friendly-name'),
    
    # Webhook Evolution
    path('webhooks/evolution/', evolution_webhook, name='evolution-webhook'),
]
