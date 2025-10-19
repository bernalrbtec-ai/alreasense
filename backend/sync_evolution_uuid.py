"""
Script para sincronizar o UUID do WhatsAppInstance para o EvolutionConnection
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.notifications.models import WhatsAppInstance

print("=" * 60)
print("🔄 SINCRONIZANDO UUID DO WHATSAPPINSTANCE")
print("=" * 60)

# Pegar a instância do WhatsAppInstance
whatsapp_instance = WhatsAppInstance.objects.filter(
    friendly_name='rbtec teste',
    is_active=True
).first()

if not whatsapp_instance:
    print("❌ WhatsAppInstance 'rbtec teste' não encontrada!")
    sys.exit(1)

print(f"\n✅ WhatsAppInstance encontrada:")
print(f"   Friendly Name: {whatsapp_instance.friendly_name}")
print(f"   Instance Name (UUID): {whatsapp_instance.instance_name}")
print(f"   Tenant: {whatsapp_instance.tenant.name}")

# Pegar o EvolutionConnection correspondente
evolution_conn = EvolutionConnection.objects.filter(
    name='rbtec teste',
    tenant=whatsapp_instance.tenant
).first()

if not evolution_conn:
    print("\n❌ EvolutionConnection 'rbtec teste' não encontrada!")
    sys.exit(1)

print(f"\n✅ EvolutionConnection encontrada:")
print(f"   Name atual: {evolution_conn.name}")
print(f"   Tenant: {evolution_conn.tenant.name}")

# Atualizar o name para o UUID
print(f"\n🔄 Atualizando name de '{evolution_conn.name}' para '{whatsapp_instance.instance_name}'...")

evolution_conn.name = whatsapp_instance.instance_name
evolution_conn.save(update_fields=['name'])

print(f"✅ EvolutionConnection atualizado!")
print(f"   Name novo: {evolution_conn.name}")

print("\n" + "=" * 60)
print("✅ SINCRONIZAÇÃO CONCLUÍDA!")
print("=" * 60)
print("\n🎉 Agora o webhook vai encontrar a connection pelo UUID!")
print("   Teste enviando uma mensagem do WhatsApp")

