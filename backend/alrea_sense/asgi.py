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
from apps.chat_messages.routing import websocket_urlpatterns as chat_messages_ws
from apps.chat.routing import websocket_urlpatterns as flow_chat_ws

# Combina rotas WebSocket
websocket_urlpatterns = chat_messages_ws + flow_chat_ws
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


def start_flow_chat_consumer():
    """
    Inicia o Flow Chat Consumer em thread separada (RabbitMQ).
    ⚠️ MANTIDO para process_incoming_media apenas (durabilidade crítica).
    """
    try:
        import asyncio
        time.sleep(12)  # Espera um pouco mais que o consumer de campanhas
        
        from apps.chat.tasks import start_chat_consumers
        
        print("🚀 [FLOW CHAT RABBITMQ] Iniciando Flow Chat Consumer (RabbitMQ)...")
        print("⚠️ [FLOW CHAT RABBITMQ] Processando apenas process_incoming_media (durabilidade crítica)")
        asyncio.run(start_chat_consumers())
        print("✅ [FLOW CHAT RABBITMQ] Consumer pronto para processar mensagens!")
            
    except Exception as e:
        print(f"❌ [FLOW CHAT RABBITMQ] Erro ao iniciar Flow Chat Consumer: {e}")


def start_redis_chat_consumer():
    """Inicia o Redis Chat Consumer em thread separada (Redis - 10x mais rápido)"""
    try:
        import asyncio
        time.sleep(14)  # Espera um pouco mais que os outros consumers
        
        from apps.chat.redis_consumer import start_redis_consumers
        
        print("🚀 [REDIS CHAT] Iniciando Redis Chat Consumer...")
        print("✅ [REDIS CHAT] Processando: send_message, fetch_profile_pic, fetch_group_info")
        asyncio.run(start_redis_consumers())
        print("✅ [REDIS CHAT] Consumer pronto para processar mensagens!")
            
    except Exception as e:
        print(f"❌ [REDIS CHAT] Erro ao iniciar Redis Chat Consumer: {e}")

# Iniciar consumers apenas se não estiver em DEBUG (produção) e não estiver desabilitado via env
disable_consumers = os.environ.get('CHAT_DISABLE_ASGI_CONSUMERS', '').strip() == '1'
if not disable_consumers and not os.environ.get('DEBUG', 'False').lower() == 'true':
    # Consumer de campanhas (RabbitMQ)
    consumer_thread = threading.Thread(target=start_rabbitmq_consumer, daemon=True)
    consumer_thread.start()
    print("🧵 [RABBITMQ] Thread do RabbitMQ Consumer iniciada")
    
    # Consumer do Flow Chat - RabbitMQ (apenas process_incoming_media)
    flow_chat_thread = threading.Thread(target=start_flow_chat_consumer, daemon=True)
    flow_chat_thread.start()
    print("🧵 [FLOW CHAT RABBITMQ] Thread do Flow Chat Consumer (RabbitMQ) iniciada")
    
    # Consumer do Flow Chat - Redis (send_message, fetch_profile_pic, fetch_group_info)
    redis_chat_thread = threading.Thread(target=start_redis_chat_consumer, daemon=True)
    redis_chat_thread.start()
    print("🧵 [REDIS CHAT] Thread do Redis Chat Consumer iniciada")
elif disable_consumers:
    print("⏸️ [ASGI] Auto-start de consumers desabilitado por CHAT_DISABLE_ASGI_CONSUMERS=1")