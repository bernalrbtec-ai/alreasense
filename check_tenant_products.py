#!/usr/bin/env python
"""
Verificar produtos do tenant
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Verificando produtos do tenant...")
    
    # Buscar tenant
    cursor.execute("SELECT id, name FROM tenancy_tenant LIMIT 1;")
    tenant = cursor.fetchone()
    
    if not tenant:
        print("❌ Nenhum tenant encontrado")
        exit(1)
    
    tenant_id, tenant_name = tenant
    print(f"🏢 Tenant: {tenant_name} (ID: {tenant_id})")
    
    # Verificar produtos do tenant
    cursor.execute("""
        SELECT 
            tp.id,
            tp.is_active,
            tp.is_addon,
            tp.activated_at,
            p.slug,
            p.name,
            p.description,
            p.requires_ui_access,
            p.addon_price
        FROM billing_tenant_product tp
        JOIN billing_product p ON tp.product_id = p.id
        WHERE tp.tenant_id = %s
        ORDER BY p.name;
    """, (tenant_id,))
    
    products = cursor.fetchall()
    
    if not products:
        print("❌ Nenhum produto encontrado para o tenant")
        
        # Verificar se existem produtos na tabela
        cursor.execute("SELECT COUNT(*) FROM billing_product;")
        total_products = cursor.fetchone()[0]
        print(f"📊 Total de produtos no sistema: {total_products}")
        
        # Listar todos os produtos
        cursor.execute("SELECT slug, name FROM billing_product ORDER BY name;")
        all_products = cursor.fetchall()
        print("📦 Produtos disponíveis:")
        for slug, name in all_products:
            print(f"   - {name} ({slug})")
    else:
        print(f"📦 Produtos do tenant ({len(products)}):")
        for tp_id, is_active, is_addon, activated_at, slug, name, description, requires_ui_access, addon_price in products:
            status = "✅ Ativo" if is_active else "❌ Inativo"
            addon_text = " (Addon)" if is_addon else ""
            ui_access = "UI" if requires_ui_access else "API"
            print(f"   - {name} ({slug}) - {status}{addon_text} - {ui_access}")
            if addon_price:
                print(f"     💰 Preço addon: R$ {addon_price}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
