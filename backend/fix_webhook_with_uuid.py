"""
Script para configurar webhook usando o UUID correto da instância
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

import requests
from apps.notifications.models import WhatsAppInstance

print("=" * 60)
print("🔧 CONFIGURANDO WEBHOOK COM UUID CORRETO")
print("=" * 60)

webhook_url = "https://alreasense-backend-production.up.railway.app/webhooks/evolution"

# Pegar a instância do WhatsAppInstance (que tem o UUID correto)
instance = WhatsAppInstance.objects.filter(
    friendly_name='rbtec teste',
    is_active=True
).first()

if not instance:
    print("❌ Instância 'rbtec teste' não encontrada no WhatsAppInstance!")
    print("\n📋 Instâncias disponíveis:")
    for inst in WhatsAppInstance.objects.all():
        print(f"   - {inst.friendly_name} ({inst.instance_name})")
    sys.exit(1)

print(f"\n✅ Instância encontrada:")
print(f"   Friendly Name: {instance.friendly_name}")
print(f"   Instance Name (UUID): {instance.instance_name}")
print(f"   API URL: {instance.api_url}")
print(f"   API Key: {instance.api_key[:20]}...")

# Configurar webhook na Evolution API usando o UUID
url = f"{instance.api_url}/webhook/set/{instance.instance_name}"

headers = {
    "Content-Type": "application/json",
    "apikey": instance.api_key
}

payload = {
    "webhook": {
        "enabled": True,
        "url": webhook_url,
        "webhook_by_events": False,
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
}

print(f"\n🔄 Configurando webhook...")
print(f"   URL API: {url}")
print(f"   Webhook URL: {webhook_url}")
print(f"   Eventos: {', '.join(payload['webhook']['events'])}")

try:
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"\n📥 Resposta:")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {response.text}")
    
    if response.status_code in [200, 201]:
        print("\n✅ WEBHOOK CONFIGURADO COM SUCESSO!")
        print(f"\n🎉 Agora você receberá:")
        print(f"   📨 Mensagens recebidas (MESSAGES_UPSERT)")
        print(f"   ✅ Status de entrega/leitura (MESSAGES_UPDATE)")
        print(f"   📤 Confirmações de envio (SEND_MESSAGE)")
    else:
        print(f"\n❌ Erro ao configurar webhook: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Erro: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

