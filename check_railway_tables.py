#!/usr/bin/env python3
"""
Script para verificar as tabelas relacionadas a produtos e tenants no Railway
"""

import psycopg2

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

print("="*80)
print("🔍 VERIFICANDO ESTRUTURA DE TABELAS NO RAILWAY")
print("="*80)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n✅ Conectado ao banco Railway!")
    
    # 1. Listar todas as tabelas
    print("\n📋 TODAS AS TABELAS:")
    print("-" * 80)
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        # Destacar tabelas relevantes
        if 'tenant' in table_name.lower() or 'product' in table_name.lower():
            print(f"   ⭐ {table_name}")
        else:
            print(f"      {table_name}")
    
    # 2. Verificar tabelas de tenant
    print("\n" + "="*80)
    print("🏢 TABELAS DE TENANT:")
    print("="*80)
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%tenant%'
        ORDER BY table_name;
    """)
    
    tenant_tables = cursor.fetchall()
    for table in tenant_tables:
        print(f"   ✅ {table[0]}")
    
    # 3. Verificar tabelas de product
    print("\n" + "="*80)
    print("📦 TABELAS DE PRODUCT:")
    print("="*80)
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%product%'
        ORDER BY table_name;
    """)
    
    product_tables = cursor.fetchall()
    for table in product_tables:
        print(f"   ✅ {table[0]}")
    
    # 4. Verificar estrutura da tabela tenant
    print("\n" + "="*80)
    print("🏢 COLUNAS DA TABELA tenancy_tenant:")
    print("="*80)
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tenancy_tenant'
        ORDER BY ordinal_position;
    """)
    
    tenant_columns = cursor.fetchall()
    for col in tenant_columns:
        print(f"   {col[0]}: {col[1]}")
    
    # 5. Verificar se tenant tem current_products
    print("\n🔍 Verificando relação tenant-products...")
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tenancy_tenant'
        AND column_name LIKE '%product%';
    """)
    
    product_cols = cursor.fetchall()
    if product_cols:
        print("   ✅ Tenant tem coluna de produtos:")
        for col in product_cols:
            print(f"      {col[0]}: {col[1]}")
    else:
        print("   ⚠️  Tenant NÃO tem coluna de produtos direta")
    
    # 6. Verificar current_products do tenant RBTec
    print("\n" + "="*80)
    print("📊 PRODUTOS DO TENANT 'RBTec Informática':")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, current_products
        FROM tenancy_tenant
        WHERE name = 'RBTec Informática';
    """)
    
    tenant = cursor.fetchone()
    if tenant:
        tenant_id, tenant_name, current_products = tenant
        print(f"   ID: {tenant_id}")
        print(f"   Nome: {tenant_name}")
        print(f"   current_products: {current_products}")
        
        if current_products:
            print(f"\n   📦 Produtos ativos (current_products):")
            # current_products é um array PostgreSQL
            cursor.execute("""
                SELECT p.id, p.name, p.slug, p.icon
                FROM billing_product p
                WHERE p.id = ANY(%s::uuid[]);
            """, (current_products,))
            
            products = cursor.fetchall()
            if products:
                for p in products:
                    print(f"      {p[3]} {p[1]} (slug: {p[2]})")
            else:
                print(f"      ⚠️  IDs não encontrados na tabela billing_product")
        else:
            print(f"\n   ⚠️  Campo current_products está VAZIO/NULL!")
            print(f"   🚨 ISSO É O PROBLEMA! Tenant sem produtos!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

