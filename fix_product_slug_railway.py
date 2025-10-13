#!/usr/bin/env python3
"""
Script para corrigir o slug do produto 'flow-contacts' para 'flow' no Railway
"""

import psycopg2
from datetime import datetime

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

print("="*80)
print("🔧 CORRIGINDO SLUG DO PRODUTO NO RAILWAY")
print("="*80)

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n✅ Conectado ao banco Railway!")
    
    # 1. Verificar produto atual
    print("\n📋 Verificando produto atual...")
    cursor.execute("""
        SELECT id, name, slug, description, requires_ui_access, is_active
        FROM billing_product
        WHERE slug = 'flow-contacts';
    """)
    
    product = cursor.fetchone()
    
    if not product:
        print("❌ Produto 'flow-contacts' não encontrado!")
        print("   Produtos disponíveis:")
        cursor.execute("SELECT slug, name FROM billing_product;")
        for p in cursor.fetchall():
            print(f"   - {p[0]}: {p[1]}")
        exit(1)
    
    product_id, name, slug, description, requires_ui, is_active = product
    print(f"\n✅ Produto encontrado:")
    print(f"   ID: {product_id}")
    print(f"   Nome: {name}")
    print(f"   Slug ATUAL: {slug} ❌")
    print(f"   UI Access: {requires_ui}")
    print(f"   Ativo: {is_active}")
    
    # 2. Verificar se já existe produto com slug 'flow'
    print("\n🔍 Verificando se slug 'flow' já existe...")
    cursor.execute("""
        SELECT id, name FROM billing_product
        WHERE slug = 'flow';
    """)
    
    existing_flow = cursor.fetchone()
    
    if existing_flow:
        print(f"⚠️  JÁ EXISTE produto com slug 'flow' (ID: {existing_flow[0]})!")
        print(f"   Nome: {existing_flow[1]}")
        print("\n🔄 Vou deletar o produto antigo 'flow-contacts' e manter o correto 'flow'")
        
        # Deletar produto errado
        cursor.execute("""
            DELETE FROM tenancy_tenantproduct
            WHERE product_id = %s;
        """, (product_id,))
        deleted_relations = cursor.rowcount
        print(f"   ✅ Removido {deleted_relations} relacionamentos tenant-produto")
        
        cursor.execute("""
            DELETE FROM billing_product
            WHERE id = %s;
        """, (product_id,))
        print(f"   ✅ Produto 'flow-contacts' deletado!")
        
    else:
        print("✅ Slug 'flow' está livre!")
        
        # 3. Atualizar slug
        print("\n🔄 Atualizando slug de 'flow-contacts' para 'flow'...")
        
        cursor.execute("""
            UPDATE billing_product
            SET slug = 'flow',
                name = 'ALREA Flow',
                description = 'Sistema completo de campanhas de disparo em massa via WhatsApp',
                icon = '📤',
                color = '#10B981',
                updated_at = %s
            WHERE id = %s;
        """, (datetime.now(), product_id))
        
        print("   ✅ Slug atualizado para 'flow'!")
    
    # Commit
    conn.commit()
    
    # 4. Verificar resultado
    print("\n📋 Verificando resultado...")
    cursor.execute("""
        SELECT id, name, slug, icon, color, is_active
        FROM billing_product
        WHERE slug = 'flow';
    """)
    
    flow_product = cursor.fetchone()
    
    if flow_product:
        print("\n✅ SUCESSO! Produto corrigido:")
        print(f"   ID: {flow_product[0]}")
        print(f"   Nome: {flow_product[1]}")
        print(f"   Slug: {flow_product[2]} ✅")
        print(f"   Ícone: {flow_product[3]}")
        print(f"   Cor: {flow_product[4]}")
        print(f"   Ativo: {flow_product[5]}")
    else:
        print("❌ Erro: produto não encontrado após atualização!")
    
    # 5. Listar todos os produtos
    print("\n" + "="*80)
    print("📦 PRODUTOS CADASTRADOS NO RAILWAY:")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, slug, icon, is_active
        FROM billing_product
        ORDER BY name;
    """)
    
    products = cursor.fetchall()
    for p in products:
        status = "🟢" if p[4] else "🔴"
        print(f"{status} {p[3]} {p[1]}")
        print(f"   Slug: {p[2]}")
        print(f"   ID: {p[0]}")
        print("-" * 80)
    
    # 6. Verificar tenants com esse produto
    print("\n📊 TENANTS COM PRODUTO FLOW:")
    print("-" * 80)
    cursor.execute("""
        SELECT t.name, t.id, tp.is_active
        FROM tenancy_tenantproduct tp
        JOIN tenancy_tenant t ON tp.tenant_id = t.id
        JOIN billing_product p ON tp.product_id = p.id
        WHERE p.slug = 'flow'
        ORDER BY t.name;
    """)
    
    tenants = cursor.fetchall()
    if tenants:
        for tenant in tenants:
            status = "🟢 Ativo" if tenant[2] else "🔴 Inativo"
            print(f"{status} {tenant[0]} (ID: {tenant[1]})")
    else:
        print("⚠️  Nenhum tenant com produto Flow!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*80)
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Faça logout e login novamente no Railway")
    print("2. Verifique se o menu 'Contatos' e 'Campanhas' apareceu")
    print("3. Se não aparecer, execute: python fix_tenant_product_railway.py")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

