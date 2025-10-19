"""
WebSocket routing para o Flow Chat.
"""
from django.urls import re_path
from apps.chat.consumers import ChatConsumer
from apps.chat.tenant_consumer import TenantChatConsumer

websocket_urlpatterns = [
    # WebSocket para grupo do tenant (novas conversas, etc)
    re_path(
        r'^ws/chat/tenant/(?P<tenant_id>[0-9a-f-]+)/$',
        TenantChatConsumer.as_asgi()
    ),
    # WebSocket para conversa específica (mensagens, status)
    re_path(
        r'^ws/chat/(?P<tenant_id>[0-9a-f-]+)/(?P<conversation_id>[0-9a-f-]+)/$',
        ChatConsumer.as_asgi()
    ),
]

