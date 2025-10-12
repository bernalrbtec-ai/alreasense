"""
Script para criar o produto 'Contacts' no sistema de billing
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.billing.models import Product
from decimal import Decimal


def create_contacts_product():
    """Cria o produto Contacts no sistema"""
    
    # Verificar se já existe
    if Product.objects.filter(slug='contacts').exists():
        print("✅ Produto 'contacts' já existe")
        product = Product.objects.get(slug='contacts')
    else:
        # Criar produto
        product = Product.objects.create(
            slug='contacts',
            name='ALREA Contacts',
            description='Sistema de contatos enriquecidos com RFM, segmentação avançada e importação em massa',
            icon='👥',
            color='#10B981',  # Verde para contatos
            is_active=True,
            requires_ui_access=True,
            addon_price=Decimal('19.90')  # Preço de instância extra se necessário
        )
        print(f"✅ Produto 'contacts' criado: {product.name}")
    
    # Mostrar informações
    print(f"\n📦 Produto: {product.name}")
    print(f"   ID: {product.id}")
    print(f"   Slug: {product.slug}")
    print(f"   Icon: {product.icon}")
    print(f"   Addon Price: R$ {product.addon_price}")
    print(f"   Active: {product.is_active}")
    
    return product


def update_plans_with_contacts():
    """Adiciona o produto Contacts aos planos existentes"""
    from apps.billing.models import Plan, PlanProduct
    
    product = Product.objects.get(slug='contacts')
    
    # Buscar todos os planos ativos
    plans = Plan.objects.filter(is_active=True)
    
    print(f"\n📋 Atualizando {plans.count()} plano(s)...")
    
    for plan in plans:
        # Verificar se já tem o produto
        if PlanProduct.objects.filter(plan=plan, product=product).exists():
            print(f"   ✅ {plan.name} já tem Contacts")
            continue
        
        # Adicionar Contacts ao plano
        # Limites sugeridos:
        # - Starter: 500 contatos
        # - Pro: 5000 contatos
        # - Enterprise: 50000 contatos
        
        if 'starter' in plan.slug.lower():
            limit = 500
        elif 'pro' in plan.slug.lower():
            limit = 5000
        elif 'enterprise' in plan.slug.lower():
            limit = 50000
        else:
            limit = 1000  # Default
        
        PlanProduct.objects.create(
            plan=plan,
            product=product,
            is_included=True,
            limit_value=limit,
            limit_unit='contatos'
        )
        
        print(f"   ✅ {plan.name}: +{limit} contatos")
    
    print("\n✅ Planos atualizados com sucesso!")


if __name__ == '__main__':
    print("🚀 Configurando produto Contacts...\n")
    
    product = create_contacts_product()
    update_plans_with_contacts()
    
    print("\n🎉 Configuração concluída!")
    print("\n💡 Próximos passos:")
    print("   1. Rodar migrations: python manage.py makemigrations contacts")
    print("   2. Aplicar migrations: python manage.py migrate")
    print("   3. Testar API: /api/contacts/contacts/")

