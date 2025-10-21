"""
WebSocket routing para o Flow Chat.

V2: Arquitetura Global WebSocket
- 1 conexão por usuário (não por conversa)
- Subscribe/Unsubscribe para trocar conversas
"""
from django.urls import re_path
from apps.chat.consumers import ChatConsumer
from apps.chat.consumers_v2 import ChatConsumerV2
from apps.chat.tenant_consumer import TenantChatConsumer

websocket_urlpatterns = [
    # ✅ V2: WebSocket GLOBAL (1 por usuário, subscribe/unsubscribe)
    re_path(
        r'^ws/chat/tenant/(?P<tenant_id>[0-9a-f-]+)/$',
        ChatConsumerV2.as_asgi()
    ),
    # ⚠️ V1: WebSocket POR CONVERSA (deprecated, manter para compatibilidade)
    re_path(
        r'^ws/chat/(?P<tenant_id>[0-9a-f-]+)/(?P<conversation_id>[0-9a-f-]+)/$',
        ChatConsumer.as_asgi()
    ),
]

