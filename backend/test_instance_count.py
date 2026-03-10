#!/usr/bin/env python
"""
Testa a contagem de instâncias do tenant
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User
from apps.notifications.models import WhatsAppInstance

email = 'paulo.bernal@rbtec.com.br'

user = User.objects.filter(email=email).first()
tenant = user.tenant

print("\n" + "="*60)
print("🧪 TESTE - CONTAGEM DE INSTÂNCIAS")
print("="*60)

print(f"\n👤 Usuário: {user.email}")
print(f"🏢 Tenant: {tenant.name}")
print(f"🆔 Tenant ID: {tenant.id}")

print(f"\n📊 Métodos do Tenant (instâncias = produto chat):")
print(f"   get_current_usage('chat', 'instances'): {tenant.get_current_usage('chat', 'instances')}")
print(f"   get_instance_limit_info(): {tenant.get_instance_limit_info()}")

print(f"\n📱 Instâncias WhatsApp diretas:")
instances = WhatsAppInstance.objects.filter(tenant=tenant)
print(f"   Total encontradas: {instances.count()}")
for instance in instances:
    print(f"   - {instance.friendly_name} ({instance.instance_name})")
    print(f"     ID: {instance.id}")
    print(f"     Tenant ID: {instance.tenant_id}")
    print(f"     Status: {instance.connection_state}")

print(f"\n🔍 Verificação manual:")
manual_count = WhatsAppInstance.objects.filter(tenant_id=tenant.id).count()
print(f"   Contagem manual por tenant_id: {manual_count}")

print(f"\n{'='*60}\n")

