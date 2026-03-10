#!/usr/bin/env python
"""
Testa os limites de instâncias para o usuário paulo.bernal@rbtec.com.br
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User
from apps.tenancy.models import Tenant
from apps.notifications.models import WhatsAppInstance

email = 'paulo.bernal@rbtec.com.br'

user = User.objects.filter(email=email).first()
tenant = user.tenant

print("\n" + "="*60)
print("🧪 TESTE - LIMITES DE INSTÂNCIAS")
print("="*60)

print(f"\n👤 Usuário: {user.email}")
print(f"🏢 Tenant: {tenant.name}")
print(f"📋 Plano: {tenant.current_plan.name if tenant.current_plan else 'Nenhum'}")

print(f"\n🔍 Verificando acesso a instâncias (produto Chat):")
has_chat = tenant.has_product('chat')
print(f"   Tem acesso ao Chat (instâncias): {has_chat}")

if has_chat:
    print(f"\n📊 Limites de instâncias (ALREA Chat):")
    limit = tenant.get_product_limit('chat', 'instances')
    current = tenant.get_current_usage('chat', 'instances')
    print(f"   Limite: {limit}")
    print(f"   Uso atual: {current}")
    print(f"   Pode criar: {current < limit if limit else True}")
    
    print(f"\n📱 Instâncias WhatsApp do tenant:")
    instances = WhatsAppInstance.objects.filter(tenant=tenant)
    print(f"   Total: {instances.count()}")
    for instance in instances:
        print(f"   - {instance.friendly_name} ({instance.instance_name}) - Status: {instance.connection_state}")

print(f"\n{'='*60}\n")

