"""
Script para verificar se existe WhatsAppInstance para RBTec
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant

print("🔍 Verificando WhatsAppInstance para RBTec...")
print("=" * 60)

rbtec = Tenant.objects.get(name="RBTec Informática")
instances = WhatsAppInstance.objects.filter(tenant=rbtec)

print(f"📱 Tenant: {rbtec.name}")
print(f"📱 Total de instâncias: {instances.count()}")

for instance in instances:
    print(f"\n📱 Instância:")
    print(f"   ID: {instance.id}")
    print(f"   Nome amigável: {instance.friendly_name}")
    print(f"   Nome técnico (instance_name): {instance.instance_name}")
    print(f"   API URL: {instance.api_url}")
    print(f"   Status: {instance.status if hasattr(instance, 'status') else 'N/A'}")
    print(f"   Ativa: {instance.is_active}")
    print(f"   Telefone: {instance.phone_number}")

print("\n" + "=" * 60)

if instances.count() == 0:
    print("❌ Nenhuma WhatsAppInstance encontrada para RBTec")
    print("\n💡 Solução:")
    print("   1. O chat deveria usar WhatsAppInstance (mesmo modelo das campanhas)")
    print("   2. Ou criar um script para migrar EvolutionConnection → WhatsAppInstance")

