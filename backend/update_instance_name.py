"""
Script para atualizar o nome da instância Evolution
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

print("🔧 Atualizando nome da instância Evolution...")
print("=" * 60)

rbtec = Tenant.objects.get(name="RBTec Informática")
conn = EvolutionConnection.objects.filter(tenant=rbtec, is_active=True).first()

print(f"📱 Conexão atual:")
print(f"   Nome antigo: '{conn.name}'")
print(f"   Base URL: {conn.base_url}")
print(f"   Status: {conn.status}")

# Atualizar nome
conn.name = "rbtec teste"
conn.save()

print(f"\n✅ Nome atualizado!")
print(f"   Nome novo: '{conn.name}'")

print(f"\n🎯 URL correta agora:")
print(f"   {conn.base_url}/message/sendText/{conn.name}")

print("\n🎉 Chat pode enviar mensagens!")

