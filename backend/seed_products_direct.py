#!/usr/bin/env python
import os
import sys
import django
import uuid

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def seed_products_direct():
    with connection.cursor() as cursor:
        print("🌱 Populando produtos e planos diretamente no banco...")
        
        # Limpar dados existentes
        print("🧹 Limpando dados existentes...")
        cursor.execute("DELETE FROM billing_plan_product;")
        cursor.execute("DELETE FROM billing_tenant_product;")
        cursor.execute("DELETE FROM billing_billinghistory;")
        cursor.execute("DELETE FROM billing_plan;")
        cursor.execute("DELETE FROM billing_product;")
        
        # Criar produtos
        print("📦 Criando produtos...")
        products = [
            {
                'id': str(uuid.uuid4()),
                'slug': 'flow',
                'name': 'ALREA Flow',
                'description': 'Sistema de campanhas WhatsApp com automação e gestão de conversas',
                'is_active': True,
                'is_addon_available': True,
                'addon_price': 99.00,
                'requires_ui_access': True,
                'icon': '💬',
                'color': '#10B981'
            },
            {
                'id': str(uuid.uuid4()),
                'slug': 'sense',
                'name': 'ALREA Sense',
                'description': 'Análise de sentimento e inteligência artificial para conversas',
                'is_active': True,
                'is_addon_available': True,
                'addon_price': 149.00,
                'requires_ui_access': True,
                'icon': '🧠',
                'color': '#8B5CF6'
            },
            {
                'id': str(uuid.uuid4()),
                'slug': 'api_public',
                'name': 'ALREA API Pública',
                'description': 'API para integração externa e desenvolvimento de aplicações',
                'is_active': True,
                'is_addon_available': False,
                'addon_price': None,
                'requires_ui_access': False,
                'icon': '🔌',
                'color': '#F59E0B'
            }
        ]
        
        for product in products:
            cursor.execute("""
                INSERT INTO billing_product 
                (id, slug, name, description, is_active, is_addon_available, 
                 addon_price, requires_ui_access, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                product['id'], product['slug'], product['name'], product['description'],
                product['is_active'], product['is_addon_available'], product['addon_price'],
                product['requires_ui_access']
            ))
            print(f"  ✅ {product['name']}")
        
        # Criar planos
        print("💳 Criando planos...")
        plans = [
            {
                'id': str(uuid.uuid4()),
                'slug': 'starter',
                'name': 'Starter',
                'description': 'Plano ideal para pequenas empresas',
                'price': 49.00,
                'billing_cycle_days': 30,
                'is_free': False,
                'max_connections': 2,
                'max_messages_per_month': 1000,
                'features': '{"campaigns": 5, "analyses": 100, "api_calls": 1000}',
                'is_active': True,
                'sort_order': 1
            },
            {
                'id': str(uuid.uuid4()),
                'slug': 'pro',
                'name': 'Pro',
                'description': 'Plano completo para empresas em crescimento',
                'price': 149.00,
                'billing_cycle_days': 30,
                'is_free': False,
                'max_connections': 10,
                'max_messages_per_month': 10000,
                'features': '{"campaigns": 50, "analyses": 1000, "api_calls": 10000}',
                'is_active': True,
                'sort_order': 2
            },
            {
                'id': str(uuid.uuid4()),
                'slug': 'api_only',
                'name': 'API Only',
                'description': 'Apenas acesso à API pública',
                'price': 99.00,
                'billing_cycle_days': 30,
                'is_free': False,
                'max_connections': 0,
                'max_messages_per_month': 0,
                'features': '{"api_calls": 5000}',
                'is_active': True,
                'sort_order': 3
            },
            {
                'id': str(uuid.uuid4()),
                'slug': 'enterprise',
                'name': 'Enterprise',
                'description': 'Solução completa para grandes empresas',
                'price': 499.00,
                'billing_cycle_days': 30,
                'is_free': False,
                'max_connections': -1,
                'max_messages_per_month': -1,
                'features': '{"campaigns": -1, "analyses": -1, "api_calls": -1}',
                'is_active': True,
                'sort_order': 4
            }
        ]
        
        for plan in plans:
            cursor.execute("""
                INSERT INTO billing_plan 
                (id, slug, name, description, price, billing_cycle_days, is_free,
                 max_connections, max_messages_per_month, features, is_active, 
                 stripe_price_id, sort_order, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                plan['id'], plan['slug'], plan['name'], plan['description'],
                plan['price'], plan['billing_cycle_days'], plan['is_free'],
                plan['max_connections'], plan['max_messages_per_month'], plan['features'],
                plan['is_active'], f"price_{plan['slug']}", plan['sort_order']
            ))
            print(f"  ✅ {plan['name']}")
        
        # Associar produtos aos planos
        print("🔗 Associando produtos aos planos...")
        
        # Buscar IDs dos produtos e planos
        cursor.execute("SELECT id, slug FROM billing_product;")
        product_ids = {slug: id for id, slug in cursor.fetchall()}
        
        cursor.execute("SELECT id, slug FROM billing_plan;")
        plan_ids = {slug: id for id, slug in cursor.fetchall()}
        
        # Starter: Flow + Sense
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['starter'], product_ids['flow'], True, 5, 'campaigns'))
        
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['starter'], product_ids['sense'], True, 100, 'analyses'))
        
        # Pro: Flow + Sense
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['pro'], product_ids['flow'], True, 50, 'campaigns'))
        
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['pro'], product_ids['sense'], True, 1000, 'analyses'))
        
        # API Only: Apenas API Pública
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['api_only'], product_ids['api_public'], True, 5000, 'api_calls'))
        
        # Enterprise: Todos os produtos ilimitados
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['enterprise'], product_ids['flow'], True, -1, 'campaigns'))
        
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['enterprise'], product_ids['sense'], True, -1, 'analyses'))
        
        cursor.execute("""
            INSERT INTO billing_plan_product 
            (id, plan_id, product_id, is_included, limit_value, limit_unit, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), plan_ids['enterprise'], product_ids['api_public'], True, -1, 'api_calls'))
        
        print("  ✅ Associações criadas")
        
        print("✅ Seed concluído com sucesso!")
        
        # Mostrar resumo
        cursor.execute("SELECT COUNT(*) FROM billing_product;")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM billing_plan;")
        plan_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM billing_plan_product;")
        association_count = cursor.fetchone()[0]
        
        print(f"\n📊 Resumo:")
        print(f"  - {product_count} produtos criados")
        print(f"  - {plan_count} planos criados")
        print(f"  - {association_count} associações plano-produto criadas")

if __name__ == "__main__":
    seed_products_direct()
