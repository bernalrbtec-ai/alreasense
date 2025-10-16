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
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

print("✅ [ASGI] Aplicação ASGI configurada com sucesso!")
print("🌐 [ASGI] Servidor pronto para receber conexões HTTP e WebSocket!")

# Iniciar RabbitMQ Consumer em thread separada (apenas em produção)
import threading
import time
import logging

logger = logging.getLogger(__name__)

def start_rabbitmq_consumer():
    """Inicia o RabbitMQ Consumer em thread separada"""
    try:
        # Aguardar um pouco para o Django estar completamente carregado
        time.sleep(10)
        
        from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
        
        consumer = get_rabbitmq_consumer()
        if consumer:
            print("🚀 [RABBITMQ] RabbitMQ Consumer (aio-pika) inicializado em background...")
            print("✅ [RABBITMQ] Consumer pronto para processar campanhas!")
        else:
            print("⚠️ [RABBITMQ] RabbitMQ Consumer não disponível - campanhas não serão processadas")
            
    except Exception as e:
        print(f"❌ [RABBITMQ] Erro ao iniciar RabbitMQ Consumer: {e}")

# Iniciar consumer apenas se não estiver em DEBUG (produção)
if not os.environ.get('DEBUG', 'False').lower() == 'true':
    consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
    consumer_thread.start()
    print("🧵 [RABBITMQ] Thread do RabbitMQ Consumer iniciada")