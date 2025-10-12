#!/usr/bin/env python
"""Criar cliente de teste para campanhas"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.tenancy.models import Tenant
from apps.authn.models import User
from apps.billing.models import Plan, TenantProduct

print("\n📋 Criando cliente de teste...")

# Criar tenant
tenant, created = Tenant.objects.get_or_create(
    name='Teste Campanhas',
    defaults={
        'status': 'active',
        'ui_access': True
    }
)

if created:
    print(f"✅ Tenant criado: {tenant.name}")
else:
    print(f"ℹ️ Tenant já existe: {tenant.name}")

# Associar plano
plan = Plan.objects.filter(slug='pro').first()
if plan:
    tenant.current_plan = plan
    tenant.save()
    print(f"✅ Plano atribuído: {plan.name}")
    
    # Ativar produtos
    for pp in plan.plan_products.all():
        tp, created = TenantProduct.objects.get_or_create(
            tenant=tenant,
            product=pp.product,
            defaults={'is_active': True}
        )
        if created:
            print(f"✅ Produto ativado: {pp.product.name}")

# Criar usuário admin
user, created = User.objects.get_or_create(
    email='teste@campanhas.com',
    defaults={
        'username': 'teste@campanhas.com',
        'first_name': 'Teste',
        'last_name': 'Campanhas',
        'tenant': tenant,
        'role': 'admin',
        'is_active': True
    }
)

if created:
    user.set_password('teste123')
    user.save()
    print(f"✅ Usuário criado: {user.email}")
else:
    print(f"ℹ️ Usuário já existe: {user.email}")

print(f"\n✅ Credenciais:")
print(f"   Email: teste@campanhas.com")
print(f"   Senha: teste123")
print(f"   Tenant: {tenant.name}")



