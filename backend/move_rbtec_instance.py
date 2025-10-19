"""
Script para mover a instância Evolution do tenant Alrea.ai para RBTec Informática
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

print("🔧 Movendo instância Evolution para RBTec Informática...")
print("=" * 60)

# Buscar tenants
try:
    rbtec_tenant = Tenant.objects.get(name="RBTec Informática")
    alrea_tenant = Tenant.objects.get(name="Alrea.ai")
    print(f"✅ Tenants encontrados:")
    print(f"   - RBTec Informática (ID: {rbtec_tenant.id})")
    print(f"   - Alrea.ai (ID: {alrea_tenant.id})")
except Tenant.DoesNotExist as e:
    print(f"❌ Erro: {e}")
    sys.exit(1)

# Buscar instância ativa do Alrea.ai
connection = EvolutionConnection.objects.filter(
    tenant=alrea_tenant,
    is_active=True,
    status='active'
).first()

if not connection:
    print("\n❌ Nenhuma instância ativa encontrada no tenant Alrea.ai")
    print("Tentando pegar qualquer uma com 'rbtec' no nome...")
    
    connection = EvolutionConnection.objects.filter(
        tenant=alrea_tenant,
        name__icontains='rbtec'
    ).first()
    
    if not connection:
        print("❌ Nenhuma instância com 'rbtec' encontrada")
        sys.exit(1)

print(f"\n📱 Instância encontrada:")
print(f"   Nome: {connection.name}")
print(f"   Tenant atual: {connection.tenant.name}")
print(f"   Status: {connection.status}")
print(f"   Is Active: {connection.is_active}")
print(f"   Base URL: {connection.base_url}")

# Mover para RBTec
print(f"\n🔄 Movendo para tenant 'RBTec Informática'...")
connection.tenant = rbtec_tenant
connection.is_active = True
connection.status = 'active'
connection.save()

print(f"\n✅ Instância movida com sucesso!")
print(f"   Nome: {connection.name}")
print(f"   Tenant NOVO: {connection.tenant.name}")
print(f"   Status: {connection.status}")
print(f"   Is Active: {connection.is_active}")

print("\n🎉 Agora o chat pode enviar mensagens!")

