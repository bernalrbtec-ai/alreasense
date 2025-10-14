#!/usr/bin/env python
"""
Análise completa da estrutura do banco de dados
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def analyze_database():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*100)
        print("🔍 ANÁLISE COMPLETA DA ESTRUTURA DO BANCO DE DADOS")
        print("="*100)
        
        # 1. TODAS AS TABELAS
        print("\n📋 TODAS AS TABELAS:")
        print("-" * 80)
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        for i, (table_name,) in enumerate(tables, 1):
            print(f"{i:2d}. {table_name}")
        
        # 2. ESTRUTURA DAS TABELAS DE BILLING
        print(f"\n🏗️ ESTRUTURA DAS TABELAS DE BILLING:")
        print("-" * 80)
        
        billing_tables = ['billing_plan', 'billing_product', 'billing_plan_product', 'billing_tenant_product', 'billing_history']
        
        for table_name in billing_tables:
            print(f"\n📊 {table_name.upper()}:")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            for col_name, data_type, is_nullable, default_val in columns:
                nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {default_val}" if default_val else ""
                print(f"   • {col_name}: {data_type} {nullable}{default}")
        
        # 3. DADOS ATUAIS DAS TABELAS DE BILLING
        print(f"\n📦 DADOS ATUAIS:")
        print("-" * 80)
        
        # Plans
        print(f"\n🎯 BILLING_PLAN:")
        cursor.execute("SELECT id, slug, name, price, is_active, sort_order FROM billing_plan ORDER BY sort_order;")
        plans = cursor.fetchall()
        for plan_id, slug, name, price, is_active, sort_order in plans:
            status = "✅ Ativo" if is_active else "❌ Inativo"
            print(f"   • {name} ({slug}) - R$ {price} - {status} - Ordem: {sort_order}")
        
        # Products
        print(f"\n📦 BILLING_PRODUCT:")
        cursor.execute("SELECT id, slug, name, description, is_active, requires_ui_access, addon_price FROM billing_product ORDER BY name;")
        products = cursor.fetchall()
        for product_id, slug, name, description, is_active, requires_ui_access, addon_price in products:
            status = "✅ Ativo" if is_active else "❌ Inativo"
            ui_access = "UI" if requires_ui_access else "API"
            price_text = f" - R$ {addon_price}" if addon_price else ""
            print(f"   • {name} ({slug}) - {status} - {ui_access}{price_text}")
            print(f"     {description[:80]}...")
        
        # Plan Products
        print(f"\n🔗 BILLING_PLAN_PRODUCT:")
        cursor.execute("""
            SELECT 
                pp.id,
                p.name as plan_name,
                p.slug as plan_slug,
                pr.name as product_name,
                pr.slug as product_slug,
                pp.is_included,
                pp.is_addon_available
            FROM billing_plan_product pp
            JOIN billing_plan p ON pp.plan_id = p.id
            JOIN billing_product pr ON pp.product_id = pr.id
            ORDER BY p.sort_order, pr.name;
        """)
        
        plan_products = cursor.fetchall()
        for pp_id, plan_name, plan_slug, product_name, product_slug, is_included, is_addon_available in plan_products:
            included = "✅ Incluído" if is_included else "❌ Não incluído"
            addon = " (Addon disponível)" if is_addon_available else ""
            print(f"   • {plan_name} → {product_name}: {included}{addon}")
        
        # Tenant Products
        print(f"\n🏢 BILLING_TENANT_PRODUCT:")
        cursor.execute("""
            SELECT 
                tp.id,
                t.name as tenant_name,
                p.name as product_name,
                p.slug as product_slug,
                tp.is_active,
                tp.is_addon,
                tp.activated_at
            FROM billing_tenant_product tp
            JOIN tenancy_tenant t ON tp.tenant_id = t.id
            JOIN billing_product p ON tp.product_id = p.id
            ORDER BY t.name, p.name;
        """)
        
        tenant_products = cursor.fetchall()
        if tenant_products:
            for tp_id, tenant_name, product_name, product_slug, is_active, is_addon, activated_at in tenant_products:
                status = "✅ Ativo" if is_active else "❌ Inativo"
                addon_text = " (Addon)" if is_addon else ""
                print(f"   • {tenant_name} → {product_name}: {status}{addon_text}")
        else:
            print("   • Nenhuma associação encontrada")
        
        # 4. TENANTS
        print(f"\n🏢 TENANTS:")
        print("-" * 80)
        cursor.execute("SELECT id, name, created_at FROM tenancy_tenant ORDER BY name;")
        tenants = cursor.fetchall()
        for tenant_id, name, created_at in tenants:
            print(f"   • {name} ({tenant_id[:8]}...) - Criado: {created_at.strftime('%d/%m/%Y')}")
        
        # 5. USUÁRIOS
        print(f"\n👤 USUÁRIOS:")
        print("-" * 80)
        cursor.execute("""
            SELECT 
                u.id,
                u.email,
                u.first_name,
                u.last_name,
                u.role,
                u.is_superuser,
                u.is_staff,
                u.is_active,
                t.name as tenant_name
            FROM authn_user u
            LEFT JOIN tenancy_tenant t ON u.tenant_id = t.id
            ORDER BY u.email;
        """)
        
        users = cursor.fetchall()
        for user_id, email, first_name, last_name, role, is_superuser, is_staff, is_active, tenant_name in users:
            status = "✅ Ativo" if is_active else "❌ Inativo"
            super_text = " (Superuser)" if is_superuser else ""
            staff_text = " (Staff)" if is_staff else ""
            tenant_text = f" - {tenant_name}" if tenant_name else " - Sem tenant"
            print(f"   • {email} - {role} - {status}{super_text}{staff_text}{tenant_text}")
        
        print(f"\n" + "="*100)
        print("✅ ANÁLISE COMPLETA FINALIZADA")
        print("="*100)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    analyze_database()
