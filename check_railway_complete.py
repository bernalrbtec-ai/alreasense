#!/usr/bin/env python3
"""
Script COMPLETO para verificar produtos e tenants no Railway
"""

import psycopg2

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

print("="*80)
print("🔍 DIAGNÓSTICO COMPLETO - RAILWAY")
print("="*80)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n✅ Conectado ao banco Railway!")
    
    # 1. PRODUTOS CADASTRADOS
    print("\n" + "="*80)
    print("📦 PRODUTOS CADASTRADOS:")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, slug, icon, color, requires_ui_access, is_active
        FROM billing_product
        ORDER BY name;
    """)
    
    products = cursor.fetchall()
    products_dict = {}
    
    for p in products:
        product_id, name, slug, icon, color, requires_ui, is_active = p
        products_dict[product_id] = {'name': name, 'slug': slug, 'icon': icon}
        
        status = "🟢 Ativo" if is_active else "🔴 Inativo"
        ui_badge = "🖥️ UI" if requires_ui else "🔌 API Only"
        
        # Verificar se slug está correto
        slug_ok = slug in ['flow', 'sense', 'api_public']
        slug_status = "✅" if slug_ok else "❌"
        
        print(f"\n{icon} {name}")
        print(f"   Slug: {slug} {slug_status}")
        print(f"   ID: {product_id}")
        print(f"   {ui_badge} | Status: {status}")
        
        if not slug_ok:
            print(f"   ⚠️  SLUG ERRADO! Frontend espera: 'flow', 'sense' ou 'api_public'")
        
        print("-" * 80)
    
    # 2. SEU USUÁRIO
    print("\n" + "="*80)
    print("👤 SEU USUÁRIO:")
    print("="*80)
    
    cursor.execute("""
        SELECT u.id, u.username, u.email, u.tenant_id, t.name as tenant_name, t.ui_access
        FROM authn_user u
        LEFT JOIN tenancy_tenant t ON u.tenant_id = t.id
        WHERE u.email = 'paulo.bernal@rbtec.com.br';
    """)
    
    user = cursor.fetchone()
    
    if not user:
        print("❌ Usuário não encontrado!")
        exit(1)
    
    user_id, username, email, tenant_id, tenant_name, tenant_ui_access = user
    print(f"   ID: {user_id}")
    print(f"   Email: {email}")
    print(f"   Username: {username}")
    print(f"   Tenant ID: {tenant_id}")
    print(f"   Tenant Nome: {tenant_name}")
    print(f"   UI Access: {'✅ Sim' if tenant_ui_access else '❌ Não'}")
    
    # 3. PRODUTOS DO TENANT
    print("\n" + "="*80)
    print(f"📊 PRODUTOS DO TENANT '{tenant_name}':")
    print("="*80)
    
    cursor.execute("""
        SELECT tp.id, p.id as product_id, p.name, p.slug, p.icon, tp.is_active, tp.created_at
        FROM billing_tenant_product tp
        JOIN billing_product p ON tp.product_id = p.id
        WHERE tp.tenant_id = %s
        ORDER BY p.name;
    """, (tenant_id,))
    
    tenant_products = cursor.fetchall()
    
    if not tenant_products:
        print("\n🚨 PROBLEMA ENCONTRADO!")
        print("❌ Tenant NÃO TEM produtos associados!")
        print("\n💡 SOLUÇÃO: Precisamos associar produtos ao tenant")
    else:
        print(f"\n✅ Tenant tem {len(tenant_products)} produto(s):")
        
        has_wrong_slug = False
        active_products = []
        
        for tp in tenant_products:
            tp_id, prod_id, prod_name, prod_slug, prod_icon, prod_active, created_at = tp
            status = "🟢 Ativo" if prod_active else "🔴 Inativo"
            
            # Verificar se slug está correto
            slug_ok = prod_slug in ['flow', 'sense', 'api_public']
            slug_status = "✅" if slug_ok else "❌"
            
            print(f"\n{status} {prod_icon} {prod_name}")
            print(f"   Slug: {prod_slug} {slug_status}")
            print(f"   Product ID: {prod_id}")
            print(f"   Tenant-Product ID: {tp_id}")
            print(f"   Criado em: {created_at}")
            
            if not slug_ok:
                has_wrong_slug = True
                print(f"   ⚠️  SLUG ERRADO! Frontend espera: 'flow', 'sense' ou 'api_public'")
            
            if prod_active:
                active_products.append(prod_slug)
            
            print("-" * 80)
    
    # 4. O QUE O FRONTEND ESPERA
    print("\n" + "="*80)
    print("🎯 O QUE O FRONTEND ESPERA:")
    print("="*80)
    print("\nLayout.tsx espera estes slugs:")
    print("   'flow'       → Menu: Contatos, Campanhas")
    print("   'sense'      → Menu: Contatos, Experimentos")
    print("   'api_public' → Menu: API Docs")
    
    # 5. DIAGNÓSTICO FINAL
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO:")
    print("="*80)
    
    if not products:
        print("\n❌ PROBLEMA 1: Nenhum produto cadastrado no sistema")
        print("   SOLUÇÃO: Executar seed de produtos")
    
    if not tenant_products:
        print("\n❌ PROBLEMA 2: Tenant sem produtos associados")
        print("   SOLUÇÃO: Associar produtos ao tenant")
    
    # Verificar slugs errados
    wrong_slugs = [p[2] for p in products if p[2] not in ['flow', 'sense', 'api_public']]
    
    if wrong_slugs:
        print(f"\n❌ PROBLEMA 3: Slugs incorretos encontrados!")
        print(f"   Slugs errados: {', '.join(wrong_slugs)}")
        print(f"   SOLUÇÃO: Corrigir slugs dos produtos")
        
        # Sugerir correções
        print(f"\n💡 CORREÇÕES SUGERIDAS:")
        for slug in wrong_slugs:
            if 'flow' in slug.lower() or 'contact' in slug.lower():
                print(f"   '{slug}' → 'flow'")
            elif 'sense' in slug.lower():
                print(f"   '{slug}' → 'sense'")
            elif 'api' in slug.lower():
                print(f"   '{slug}' → 'api_public'")
    
    if tenant_products and not wrong_slugs:
        print("\n✅ Tudo parece correto!")
        print("   Produtos cadastrados: ✅")
        print("   Tenant com produtos: ✅")
        print("   Slugs corretos: ✅")
        print("\n💡 Se ainda não está funcionando:")
        print("   1. Faça logout e login novamente")
        print("   2. Limpe o cache do navegador (Ctrl+Shift+R)")
        print("   3. Verifique se os produtos estão ativos (is_active=true)")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

