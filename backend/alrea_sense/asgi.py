"""
ASGI config for alrea_sense project.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

print("🚀 [ASGI] Iniciando configuração ASGI...")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')

print("🚀 [ASGI] Carregando aplicação Django...")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

print("✅ [ASGI] Aplicação Django carregada!")

print("🚀 [ASGI] Carregando rotas WebSocket...")
from apps.chat_messages.routing import websocket_urlpatterns
print(f"✅ [ASGI] {len(websocket_urlpatterns)} rotas WebSocket carregadas!")

print("🚀 [ASGI] Configurando ProtocolTypeRouter...")
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})

print("✅ [ASGI] Aplicação ASGI configurada com sucesso!")
print("🌐 [ASGI] Servidor pronto para receber conexões HTTP e WebSocket!")
