"""
Script para configurar webhook do chat na Evolution API
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

import requests
from apps.connections.models import EvolutionConnection

print("=" * 60)
print("🔧 CONFIGURANDO WEBHOOK DO CHAT")
print("=" * 60)

webhook_url = "https://alreasense-backend-production.up.railway.app/webhooks/evolution"

# Pegar a conexão ativa
conn = EvolutionConnection.objects.filter(name='rbtec teste', is_active=True).first()

if not conn:
    print("❌ Conexão 'rbtec teste' não encontrada!")
    sys.exit(1)

print(f"\n✅ Conexão encontrada: {conn.name}")
print(f"   Base URL: {conn.base_url}")
print(f"   API Key: {conn.api_key[:20]}...")

# Configurar webhook na Evolution API
url = f"{conn.base_url}/webhook/set/{conn.name}"

headers = {
    "Content-Type": "application/json",
    "apikey": conn.api_key
}

payload = {
    "url": webhook_url,
    "webhook_by_events": False,  # Enviar todos os eventos para a mesma URL
    "webhook_base64": False,
    "events": [
        "QRCODE_UPDATED",
        "MESSAGES_SET",
        "MESSAGES_UPSERT",
        "MESSAGES_UPDATE",
        "MESSAGES_DELETE",
        "SEND_MESSAGE",
        "CONNECTION_UPDATE"
    ]
}

print(f"\n🔄 Configurando webhook...")
print(f"   URL: {url}")
print(f"   Webhook URL: {webhook_url}")
print(f"   Eventos: {len(payload['events'])}")

try:
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"\n📥 Resposta:")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {response.text[:500]}")
    
    if response.status_code in [200, 201]:
        print("\n✅ WEBHOOK CONFIGURADO COM SUCESSO!")
        
        # Atualizar no banco
        conn.webhook_url = webhook_url
        conn.save(update_fields=['webhook_url'])
        print(f"✅ Webhook URL salvo no banco de dados")
    else:
        print(f"\n❌ Erro ao configurar webhook: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Erro: {e}")

print("\n" + "=" * 60)

