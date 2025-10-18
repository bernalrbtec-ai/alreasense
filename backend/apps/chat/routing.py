"""
WebSocket routing para o Flow Chat.
"""
from django.urls import re_path
from apps.chat.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/chat/(?P<tenant_id>[0-9a-f-]+)/(?P<conversation_id>[0-9a-f-]+)/$',
        ChatConsumer.as_asgi()
    ),
]

