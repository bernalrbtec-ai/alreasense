"""
WebSocket routing para o Flow Chat.

Arquitetura Global WebSocket:
- 1 conexão por usuário (não por conversa)
- Subscribe/Unsubscribe para trocar conversas
- Escalável para múltiplas conversas simultâneas
"""
from django.urls import re_path
from apps.chat.consumers_v2 import ChatConsumerV2
from apps.chat.tenant_consumer import TenantChatConsumer

websocket_urlpatterns = [
    # ✅ WebSocket GLOBAL (1 por usuário, subscribe/unsubscribe)
    re_path(
        r'^ws/chat/tenant/(?P<tenant_id>[0-9a-f-]+)/$',
        ChatConsumerV2.as_asgi()
    ),
    # ❌ V1 REMOVIDO: WebSocket por conversa (deprecated)
    # Causava múltiplas conexões e código duplicado
]

