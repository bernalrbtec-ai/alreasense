#!/usr/bin/env python
"""
Script para debugar acesso do usuário aos produtos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User
from apps.tenancy.models import Tenant
from apps.billing.models import TenantProduct

email = 'paulo.bernal@rbtec.com.br'

user = User.objects.filter(email=email).first()

if not user:
    print(f"❌ Usuário {email} não encontrado!")
    exit(1)

print(f"\n{'='*60}")
print(f"🔍 DEBUG - ACESSO DO USUÁRIO")
print(f"{'='*60}")

print(f"\n📧 USUÁRIO")
print(f"   Email: {user.email}")
print(f"   Nome: {user.first_name} {user.last_name}")
print(f"   Role: {user.role}")
print(f"   Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")
print(f"   Tenant ID: {user.tenant.id if user.tenant else 'Nenhum'}")

if user.tenant:
    tenant = user.tenant
    
    print(f"\n📋 PLANO ATUAL")
    if tenant.current_plan:
        print(f"   Nome: {tenant.current_plan.name}")
        print(f"   Slug: {tenant.current_plan.slug}")
        print(f"   Preço: R$ {tenant.current_plan.price}")
        
        print(f"\n📦 PRODUTOS DO PLANO")
        plan_products = tenant.current_plan.plan_products.all()
        if plan_products:
            for pp in plan_products:
                print(f"   - {pp.product.name} ({pp.product.slug})")
                print(f"     Limite: {pp.limit_value} {pp.limit_unit}")
                print(f"     Incluído: {'Sim' if pp.is_included else 'Não'}")
        else:
            print(f"   ⚠️  Nenhum produto no plano!")
    else:
        print(f"   ⚠️  Nenhum plano atribuído!")
    
    print(f"\n✅ PRODUTOS ATIVOS DO TENANT")
    tenant_products = TenantProduct.objects.filter(tenant=tenant)
    if tenant_products:
        for tp in tenant_products:
            print(f"   - {tp.product.name} ({tp.product.slug})")
            print(f"     Ativo: {'Sim' if tp.is_active else 'Não'}")
            print(f"     Ativado em: {tp.activated_at}")
    else:
        print(f"   ⚠️  Nenhum produto ativo no tenant!")
    
    print(f"\n🔑 SLUGS DOS PRODUTOS ATIVOS")
    active_slugs = tenant.active_product_slugs
    print(f"   {active_slugs}")
    
    print(f"\n🎯 VERIFICAÇÃO DE ACESSO")
    products_to_check = ['flow', 'sense', 'contacts', 'api_public']
    for prod_slug in products_to_check:
        has_access = tenant.has_product(prod_slug)
        print(f"   {prod_slug}: {'✅ TEM ACESSO' if has_access else '❌ SEM ACESSO'}")

print(f"\n{'='*60}\n")

