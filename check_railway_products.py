#!/usr/bin/env python3
"""
Script para APENAS VERIFICAR os produtos cadastrados no Railway
NÃO FAZ NENHUMA ALTERAÇÃO - APENAS CONSULTA
"""

import psycopg2

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

print("="*80)
print("🔍 VERIFICANDO PRODUTOS NO RAILWAY")
print("   (Apenas consulta - NÃO faz alterações)")
print("="*80)

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n✅ Conectado ao banco Railway!")
    
    # 1. Listar TODOS os produtos
    print("\n" + "="*80)
    print("📦 PRODUTOS CADASTRADOS:")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, slug, icon, color, requires_ui_access, is_active, addon_price
        FROM billing_product
        ORDER BY name;
    """)
    
    products = cursor.fetchall()
    
    if not products:
        print("⚠️  Nenhum produto cadastrado!")
    else:
        for p in products:
            product_id, name, slug, icon, color, requires_ui, is_active, addon_price = p
            status = "🟢 Ativo" if is_active else "🔴 Inativo"
            ui_badge = "🖥️ UI" if requires_ui else "🔌 API Only"
            price = f"R$ {addon_price}" if addon_price else "Incluído"
            
            print(f"\n{icon} {name}")
            print(f"   Slug: {slug}")
            print(f"   ID: {product_id}")
            print(f"   {ui_badge} | Addon: {price}")
            print(f"   Status: {status}")
            print(f"   Cor: {color}")
            print("-" * 80)
    
    # 2. Verificar tenant do usuário (paulo.bernal@rbtec.com.br)
    print("\n" + "="*80)
    print("👤 VERIFICANDO SEU USUÁRIO:")
    print("="*80)
    
    cursor.execute("""
        SELECT u.id, u.username, u.email, t.id as tenant_id, t.name as tenant_name
        FROM authn_user u
        LEFT JOIN tenancy_tenant t ON u.tenant_id = t.id
        WHERE u.email = 'paulo.bernal@rbtec.com.br';
    """)
    
    user = cursor.fetchone()
    
    if user:
        user_id, username, email, tenant_id, tenant_name = user
        print(f"\n✅ Usuário encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Tenant Nome: {tenant_name}")
        
        # 3. Verificar produtos do tenant
        if tenant_id:
            print("\n" + "="*80)
            print(f"📊 PRODUTOS DO TENANT '{tenant_name}':")
            print("="*80)
            
            cursor.execute("""
                SELECT p.id, p.name, p.slug, p.icon, tp.is_active
                FROM tenancy_tenantproduct tp
                JOIN billing_product p ON tp.product_id = p.id
                WHERE tp.tenant_id = %s
                ORDER BY p.name;
            """, (tenant_id,))
            
            tenant_products = cursor.fetchall()
            
            if not tenant_products:
                print("⚠️  Nenhum produto associado a este tenant!")
                print("\n💡 ISSO É O PROBLEMA! Tenant sem produtos!")
            else:
                for tp in tenant_products:
                    prod_id, prod_name, prod_slug, prod_icon, prod_active = tp
                    status = "🟢 Ativo" if prod_active else "🔴 Inativo"
                    print(f"\n{status} {prod_icon} {prod_name}")
                    print(f"   Slug: {prod_slug}")
                    print(f"   ID: {prod_id}")
                    print("-" * 80)
        else:
            print("\n⚠️  Usuário SEM tenant associado!")
    else:
        print("\n❌ Usuário não encontrado!")
    
    # 4. Verificar o que o Layout.tsx espera
    print("\n" + "="*80)
    print("🎯 O QUE O FRONTEND ESPERA:")
    print("="*80)
    print("\nO arquivo Layout.tsx espera estes slugs:")
    print("   ✅ 'flow'       → Contatos, Campanhas")
    print("   ✅ 'sense'      → Contatos, Experimentos")
    print("   ✅ 'api_public' → API Docs")
    print("\nSlugs encontrados no banco:")
    
    cursor.execute("SELECT slug FROM billing_product ORDER BY slug;")
    slugs = cursor.fetchall()
    for s in slugs:
        slug = s[0]
        if slug in ['flow', 'sense', 'api_public']:
            print(f"   ✅ '{slug}' ← CORRETO")
        else:
            print(f"   ❌ '{slug}' ← ERRADO (frontend não reconhece)")
    
    # 5. Diagnóstico final
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO:")
    print("="*80)
    
    if not products:
        print("\n❌ PROBLEMA: Nenhum produto cadastrado!")
        print("   SOLUÇÃO: Executar script para criar produtos")
    elif not tenant_products if user and tenant_id else True:
        print("\n❌ PROBLEMA: Tenant sem produtos associados!")
        print("   SOLUÇÃO: Executar script para associar produtos ao tenant")
    else:
        # Verificar se tem slug errado
        wrong_slugs = [s[0] for s in slugs if s[0] not in ['flow', 'sense', 'api_public']]
        if wrong_slugs:
            print(f"\n⚠️ PROBLEMA ENCONTRADO: Slugs incorretos!")
            print(f"   Slugs errados: {', '.join(wrong_slugs)}")
            print(f"   SOLUÇÃO: Corrigir slugs ou deletar produtos errados")
        else:
            print("\n✅ PRODUTOS PARECEM CORRETOS!")
            print("   Verifique se o tenant está ativo e com produtos ativos")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

