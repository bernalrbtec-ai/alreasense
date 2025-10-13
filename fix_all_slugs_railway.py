#!/usr/bin/env python3
"""
Script para corrigir TODOS os slugs errados no Railway
"""

import psycopg2
from datetime import datetime

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

print("="*80)
print("🔧 CORRIGINDO SLUGS DOS PRODUTOS NO RAILWAY")
print("="*80)

# Mapeamento de correções
CORRECTIONS = {
    'flow-contacts': {
        'new_slug': 'flow',
        'new_name': 'ALREA Flow',
        'new_description': 'Sistema completo de campanhas de disparo em massa via WhatsApp',
        'new_icon': '📤',
        'new_color': '#10B981',
    },
    'api-only': {
        'new_slug': 'api_public',
        'new_name': 'ALREA API Pública',
        'new_description': 'Endpoints REST documentados para integração com sistemas externos',
        'new_icon': '🔌',
        'new_color': '#F59E0B',
    },
}

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("\n✅ Conectado ao banco Railway!")
    
    # Listar produtos que precisam correção
    print("\n📋 Verificando produtos a corrigir...")
    print("-" * 80)
    
    for old_slug, corrections in CORRECTIONS.items():
        cursor.execute("""
            SELECT id, name, slug
            FROM billing_product
            WHERE slug = %s;
        """, (old_slug,))
        
        product = cursor.fetchone()
        
        if product:
            product_id, name, slug = product
            new_slug = corrections['new_slug']
            new_name = corrections['new_name']
            
            print(f"\n✅ Produto encontrado:")
            print(f"   ID: {product_id}")
            print(f"   Nome atual: {name}")
            print(f"   Slug atual: {slug} ❌")
            print(f"   Novo slug: {new_slug} ✅")
            print(f"   Novo nome: {new_name}")
            
            # Verificar se novo slug já existe
            cursor.execute("""
                SELECT id, name
                FROM billing_product
                WHERE slug = %s;
            """, (new_slug,))
            
            existing = cursor.fetchone()
            
            if existing and existing[0] != product_id:
                print(f"   ⚠️  JÁ EXISTE outro produto com slug '{new_slug}'!")
                print(f"      ID conflitante: {existing[0]}")
                print(f"      Nome: {existing[1]}")
                print(f"   ⏭️  Pulando este produto...")
                continue
            
            # Atualizar slug
            print(f"   🔄 Atualizando...")
            
            cursor.execute("""
                UPDATE billing_product
                SET slug = %s,
                    name = %s,
                    description = %s,
                    icon = %s,
                    color = %s,
                    updated_at = %s
                WHERE id = %s;
            """, (
                corrections['new_slug'],
                corrections['new_name'],
                corrections['new_description'],
                corrections['new_icon'],
                corrections['new_color'],
                datetime.now(),
                product_id,
            ))
            
            print(f"   ✅ Produto atualizado com sucesso!")
        else:
            print(f"\n⏭️  Produto '{old_slug}' não encontrado (já foi corrigido?)")
    
    # Commit
    conn.commit()
    
    # Verificar resultado
    print("\n" + "="*80)
    print("📦 PRODUTOS APÓS CORREÇÃO:")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, slug, icon, is_active
        FROM billing_product
        ORDER BY name;
    """)
    
    products = cursor.fetchall()
    
    for p in products:
        product_id, name, slug, icon, is_active = p
        status = "🟢" if is_active else "🔴"
        
        # Verificar se slug está correto agora
        slug_ok = slug in ['flow', 'sense', 'api_public']
        slug_status = "✅" if slug_ok else "❌"
        
        print(f"\n{status} {icon} {name}")
        print(f"   Slug: {slug} {slug_status}")
        print(f"   ID: {product_id}")
        print("-" * 80)
    
    # Verificar se ainda há produtos com slug errado
    wrong_slugs = [p[2] for p in products if p[2] not in ['flow', 'sense', 'api_public']]
    
    if wrong_slugs:
        print(f"\n⚠️  AINDA HÁ SLUGS ERRADOS:")
        for slug in wrong_slugs:
            print(f"   ❌ {slug}")
        print("\n💡 Execute o script novamente ou corrija manualmente")
    else:
        print(f"\n✅ TODOS OS SLUGS ESTÃO CORRETOS!")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*80)
    print("✅ CORREÇÃO CONCLUÍDA")
    print("="*80)
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Faça logout e login novamente no Railway")
    print("2. Limpe o cache do navegador (Ctrl+Shift+R)")
    print("3. Verifique se o menu 'Contatos' e 'Campanhas' apareceu")
    print("\n💡 Pode levar até 1 minuto para o cache atualizar")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

