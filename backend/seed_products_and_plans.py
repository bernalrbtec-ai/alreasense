#!/usr/bin/env python
"""
Seed de produtos e planos iniciais conforme ALREA_PRODUCTS_STRATEGY.md
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.billing.models import Product, Plan, PlanProduct
from apps.tenancy.models import Tenant

def create_products():
    """Criar os 3 produtos principais"""
    
    products_data = [
        {
            'slug': 'flow',
            'name': 'ALREA Flow',
            'description': 'Sistema completo de campanhas de disparo em massa via WhatsApp',
            'icon': '📤',
            'color': '#3B82F6',  # Blue
            'is_active': True,
            'requires_ui_access': True,
            'addon_price': None,  # Não é add-on, é produto base
        },
        {
            'slug': 'sense',
            'name': 'ALREA Sense',
            'description': 'Monitoramento e análise de conversas WhatsApp com IA',
            'icon': '🧠',
            'color': '#8B5CF6',  # Purple
            'is_active': True,
            'requires_ui_access': True,
            'addon_price': None,  # Não é add-on, é produto base
        },
        {
            'slug': 'api_public',
            'name': 'ALREA API Pública',
            'description': 'Endpoints REST documentados para integração com sistemas externos',
            'icon': '🔌',
            'color': '#10B981',  # Green
            'is_active': True,
            'requires_ui_access': False,  # API não precisa de UI
            'addon_price': 79.00,  # Pode ser add-on
        },
    ]
    
    print("🛠️  Criando produtos...")
    
    for data in products_data:
        product, created = Product.objects.get_or_create(
            slug=data['slug'],
            defaults=data
        )
        
        if created:
            print(f"  ✅ Criado: {product.icon} {product.name}")
        else:
            print(f"  ♻️  Já existe: {product.icon} {product.name}")
    
    return Product.objects.all()

def create_plans():
    """Criar os 4 planos principais"""
    
    plans_data = [
        {
            'slug': 'starter',
            'name': 'Starter',
            'description': 'Ideal para pequenas empresas e autônomos',
            'price': 49.00,
            'color': '#3B82F6',  # Blue
            'is_active': True,
            'sort_order': 1,
        },
        {
            'slug': 'pro',
            'name': 'Pro',
            'description': 'Solução completa para empresas em crescimento',
            'price': 149.00,
            'color': '#8B5CF6',  # Purple
            'is_active': True,
            'sort_order': 2,
        },
        {
            'slug': 'api_only',
            'name': 'API Only',
            'description': 'Para desenvolvedores e integradores',
            'price': 99.00,
            'color': '#10B981',  # Green
            'is_active': True,
            'sort_order': 3,
        },
        {
            'slug': 'enterprise',
            'name': 'Enterprise',
            'description': 'Tudo ilimitado para grandes empresas',
            'price': 499.00,
            'color': '#F59E0B',  # Orange
            'is_active': True,
            'sort_order': 4,
        },
    ]
    
    print("\n🛠️  Criando planos...")
    
    for data in plans_data:
        plan, created = Plan.objects.get_or_create(
            slug=data['slug'],
            defaults=data
        )
        
        if created:
            print(f"  ✅ Criado: {plan.name} (R$ {plan.price:.2f})")
        else:
            print(f"  ♻️  Já existe: {plan.name} (R$ {plan.price:.2f})")
    
    return Plan.objects.all()

def create_plan_products():
    """Criar relacionamentos Plan-Product conforme especificação"""
    
    print("\n🛠️  Configurando produtos por plano...")
    
    # Mapeamento conforme ALREA_PRODUCTS_STRATEGY.md
    plan_products_config = {
        'starter': {
            'flow': {'is_included': True, 'limit_value': 5, 'limit_unit': 'campanhas/mês', 'is_addon_available': False},
            'sense': {'is_included': False, 'limit_value': None, 'limit_unit': None, 'is_addon_available': False},
            'api_public': {'is_included': False, 'limit_value': None, 'limit_unit': None, 'is_addon_available': True},
        },
        'pro': {
            'flow': {'is_included': True, 'limit_value': 20, 'limit_unit': 'campanhas/mês', 'is_addon_available': False},
            'sense': {'is_included': True, 'limit_value': 5000, 'limit_unit': 'análises/mês', 'is_addon_available': False},
            'api_public': {'is_included': False, 'limit_value': None, 'limit_unit': None, 'is_addon_available': True},
        },
        'api_only': {
            'flow': {'is_included': False, 'limit_value': None, 'limit_unit': None, 'is_addon_available': False},
            'sense': {'is_included': False, 'limit_value': None, 'limit_unit': None, 'is_addon_available': False},
            'api_public': {'is_included': True, 'limit_value': 50000, 'limit_unit': 'requests/dia', 'is_addon_available': False},
        },
        'enterprise': {
            'flow': {'is_included': True, 'limit_value': None, 'limit_unit': 'ilimitado', 'is_addon_available': False},
            'sense': {'is_included': True, 'limit_value': None, 'limit_unit': 'ilimitado', 'is_addon_available': False},
            'api_public': {'is_included': True, 'limit_value': None, 'limit_unit': 'ilimitado', 'is_addon_available': False},
        },
    }
    
    for plan_slug, products_config in plan_products_config.items():
        try:
            plan = Plan.objects.get(slug=plan_slug)
            print(f"\n  📋 Plano: {plan.name}")
            
            for product_slug, config in products_config.items():
                try:
                    product = Product.objects.get(slug=product_slug)
                    
                    plan_product, created = PlanProduct.objects.get_or_create(
                        plan=plan,
                        product=product,
                        defaults=config
                    )
                    
                    if created:
                        status = "✅ Incluído" if config['is_included'] else "❌ Não incluído"
                        if config['is_addon_available']:
                            status += " (Add-on disponível)"
                        print(f"    {product.icon} {product.name}: {status}")
                    else:
                        print(f"    ♻️  {product.icon} {product.name}: Já configurado")
                        
                except Product.DoesNotExist:
                    print(f"    ❌ Produto não encontrado: {product_slug}")
                    
        except Plan.DoesNotExist:
            print(f"  ❌ Plano não encontrado: {plan_slug}")

def show_summary():
    """Mostrar resumo da configuração"""
    
    print("\n" + "="*60)
    print("📊 RESUMO DA CONFIGURAÇÃO")
    print("="*60)
    
    # Produtos
    print("\n📦 PRODUTOS:")
    for product in Product.objects.all():
        addon_info = f" (Add-on: R$ {product.addon_price:.2f})" if product.addon_price else ""
        print(f"  {product.icon} {product.name}{addon_info}")
    
    # Planos
    print("\n💰 PLANOS:")
    for plan in Plan.objects.all():
        print(f"  {plan.name}: R$ {plan.price:.2f}/mês")
    
    # Plan-Product matrix
    print("\n🔗 MATRIZ PLANO-PRODUTO:")
    print("┌─────────────┬─────────┬──────┬──────────┬────────────┐")
    print("│ Plano       │ Flow    │ Sense│ API      │ Preço      │")
    print("├─────────────┼─────────┼──────┼──────────┼────────────┤")
    
    for plan in Plan.objects.all().order_by('sort_order'):
        flow_status = "✅" if plan.plan_products.filter(product__slug='flow', is_included=True).exists() else "❌"
        sense_status = "✅" if plan.plan_products.filter(product__slug='sense', is_included=True).exists() else "❌"
        api_status = "✅" if plan.plan_products.filter(product__slug='api_public', is_included=True).exists() else "❌"
        
        print(f"│ {plan.name:<11} │ {flow_status:<7} │ {sense_status:<4} │ {api_status:<8} │ R$ {plan.price:>6.2f} │")
    
    print("└─────────────┴─────────┴──────┴──────────┴────────────┘")
    
    # Add-ons disponíveis
    print("\n🔌 ADD-ONS DISPONÍVEIS:")
    for plan in Plan.objects.all():
        addons = plan.plan_products.filter(is_addon_available=True)
        if addons.exists():
            addon_list = []
            for pp in addons:
                if pp.product.addon_price:
                    addon_list.append(f"{pp.product.name} (+R$ {pp.product.addon_price:.2f})")
                else:
                    addon_list.append(f"{pp.product.name} (preço não definido)")
            print(f"  {plan.name}: {', '.join(addon_list)}")
        else:
            print(f"  {plan.name}: Nenhum add-on")

def main():
    """Executar seed completo"""
    
    print("🚀 ALREA - Seed de Produtos e Planos")
    print("="*50)
    
    try:
        # Criar produtos
        products = create_products()
        
        # Criar planos
        plans = create_plans()
        
        # Configurar relacionamentos
        create_plan_products()
        
        # Mostrar resumo
        show_summary()
        
        print("\n✅ Seed concluído com sucesso!")
        print("\n📋 Próximos passos:")
        print("  1. Acesse Admin → Billing → Products")
        print("  2. Acesse Admin → Billing → Plans")
        print("  3. Verifique configurações")
        print("  4. Teste criação de tenant com plano")
        
    except Exception as e:
        print(f"\n❌ Erro durante seed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
