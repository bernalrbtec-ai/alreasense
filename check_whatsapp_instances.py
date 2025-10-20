"""
Script para verificar WhatsAppInstances no banco.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

print("\n" + "="*80)
print("📱 WHATSAPP INSTANCES")
print("="*80)

instances = WhatsAppInstance.objects.all()
print(f"\n✅ Total: {instances.count()} instâncias\n")

for instance in instances:
    print(f"📱 WhatsAppInstance:")
    print(f"   ID: {instance.id}")
    print(f"   Tenant: {instance.tenant.name if instance.tenant else 'N/A'}")
    print(f"   instance_name: '{instance.instance_name}'")
    print(f"   phone: {instance.phone}")
    print(f"   is_active: {instance.is_active}")
    print(f"   status: {instance.status}")
    print()

print("\n" + "="*80)
print("🔌 EVOLUTION CONNECTIONS")
print("="*80)

connections = EvolutionConnection.objects.all()
print(f"\n✅ Total: {connections.count()} conexões\n")

for conn in connections:
    print(f"🔌 EvolutionConnection:")
    print(f"   ID: {conn.id}")
    print(f"   Tenant: {conn.tenant.name if conn.tenant else 'N/A'}")
    print(f"   name: '{conn.name}'")
    print(f"   base_url: {conn.base_url}")
    print(f"   is_active: {conn.is_active}")
    print(f"   status: {conn.status}")
    print()

print("\n" + "="*80)
print("🔍 ANÁLISE")
print("="*80)

print("\n🔍 Buscando pelo nome 'RBTec'...")
print("\n   WhatsAppInstance.objects.filter(instance_name='RBTec'):")
wai = WhatsAppInstance.objects.filter(instance_name='RBTec')
print(f"   Resultado: {wai.count()} encontrada(s)")
for i in wai:
    print(f"      - {i.instance_name} (Tenant: {i.tenant.name})")

print("\n   EvolutionConnection.objects.filter(name='RBTec'):")
ec = EvolutionConnection.objects.filter(name='RBTec')
print(f"   Resultado: {ec.count()} encontrada(s)")
for c in ec:
    print(f"      - {c.name} (Tenant: {c.tenant.name})")

print("\n" + "="*80)
print("💡 SUGESTÃO")
print("="*80)
print("\nO webhook está enviando: instance_name='RBTec'")
print("Precisamos que haja uma WhatsAppInstance com instance_name='RBTec'")
print("\n")

