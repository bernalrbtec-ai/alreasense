#!/usr/bin/env python
"""
Script para adicionar produto Contacts aos planos que têm Flow
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.billing.models import Plan, Product, PlanProduct, TenantProduct
from apps.tenancy.models import Tenant

print("\n" + "="*60)
print("🔧 ADICIONANDO CONTACTS AOS PLANOS COM FLOW")
print("="*60)

# Buscar produto Contacts
contacts_product = Product.objects.filter(slug='contacts').first()
if not contacts_product:
    print("\n❌ Produto 'contacts' não existe! Criando...")
    contacts_product = Product.objects.create(
        slug='contacts',
        name='ALREA Contacts',
        description='Gerenciamento de contatos, listas e segmentação',
        is_active=True
    )
    print(f"✅ Produto Contacts criado: {contacts_product.name}")
else:
    print(f"\n✅ Produto Contacts encontrado: {contacts_product.name}")

# Buscar todos os planos que têm Flow
plans_with_flow = Plan.objects.filter(plan_products__product__slug='flow').distinct()

print(f"\n📋 Planos com Flow: {plans_with_flow.count()}")

for plan in plans_with_flow:
    print(f"\n   Processando plano: {plan.name}")
    
    # Verificar se já tem Contacts
    has_contacts = plan.plan_products.filter(product__slug='contacts').exists()
    
    if has_contacts:
        print(f"   ⚠️  Já tem Contacts")
    else:
        # Adicionar Contacts ao plano
        PlanProduct.objects.create(
            plan=plan,
            product=contacts_product,
            limit_value=1000,  # Limite padrão de contatos
            limit_unit='contatos',
            is_included=True
        )
        print(f"   ✅ Contacts adicionado ao plano")
    
    # Ativar Contacts para todos os tenants com este plano
    tenants_with_plan = Tenant.objects.filter(current_plan=plan)
    print(f"   📊 Tenants com este plano: {tenants_with_plan.count()}")
    
    for tenant in tenants_with_plan:
        # Verificar se tenant já tem Contacts ativo
        tenant_has_contacts = TenantProduct.objects.filter(
            tenant=tenant,
            product=contacts_product
        ).exists()
        
        if not tenant_has_contacts:
            # Ativar Contacts para o tenant
            TenantProduct.objects.create(
                tenant=tenant,
                product=contacts_product,
                is_active=True
            )
            print(f"      ✅ Contacts ativado para {tenant.name}")
        else:
            # Garantir que está ativo
            tp = TenantProduct.objects.get(tenant=tenant, product=contacts_product)
            if not tp.is_active:
                tp.is_active = True
                tp.save()
                print(f"      ✅ Contacts reativado para {tenant.name}")
            else:
                print(f"      ⚠️  {tenant.name} já tem Contacts ativo")

print(f"\n{'='*60}")
print("✅ CONCLUÍDO!")
print("="*60 + "\n")


