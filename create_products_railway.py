import psycopg2
import uuid
from datetime import datetime

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

# Produtos a serem criados
products_data = [
    {
        'name': 'API Only',
        'slug': 'api-only',
        'description': 'Acesso apenas via API, sem interface web',
        'requires_ui_access': False,
        'addon_price': None,
        'is_active': True,
        'icon': '🔌',
        'color': '#10B981',
    },
    {
        'name': 'Flow + Contatos',
        'slug': 'flow-contacts',
        'description': 'Módulo de automação de fluxos e gerenciamento de contatos',
        'requires_ui_access': True,
        'addon_price': '0.00',
        'is_active': True,
        'icon': '📊',
        'color': '#8B5CF6',
    },
]

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Conectado ao banco Railway!")
    print("\n" + "="*80)
    
    for product_data in products_data:
        print(f"\n📦 Criando produto: {product_data['name']}")
        print(f"   Slug: {product_data['slug']}")
        print(f"   UI Access: {product_data['requires_ui_access']}")
        print(f"   Addon Price: R$ {product_data['addon_price'] or '0.00'}")
        
        # Verificar se o produto já existe
        cursor.execute("""
            SELECT id, name FROM billing_product
            WHERE slug = %s;
        """, (product_data['slug'],))
        
        existing = cursor.fetchone()
        
        if existing:
            print(f"   ⚠️  Produto já existe (ID: {existing[0]})")
            print(f"   🔄 Atualizando...")
            
            cursor.execute("""
                UPDATE billing_product
                SET name = %s,
                    description = %s,
                    requires_ui_access = %s,
                    addon_price = %s,
                    is_active = %s,
                    icon = %s,
                    color = %s,
                    updated_at = %s
                WHERE slug = %s;
            """, (
                product_data['name'],
                product_data['description'],
                product_data['requires_ui_access'],
                product_data['addon_price'],
                product_data['is_active'],
                product_data['icon'],
                product_data['color'],
                datetime.now(),
                product_data['slug'],
            ))
            
            print(f"   ✅ Produto atualizado!")
        else:
            # Criar novo produto
            product_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO billing_product (
                    id, name, slug, description, requires_ui_access, addon_price,
                    is_active, icon, color, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                product_id,
                product_data['name'],
                product_data['slug'],
                product_data['description'],
                product_data['requires_ui_access'],
                product_data['addon_price'],
                product_data['is_active'],
                product_data['icon'],
                product_data['color'],
                datetime.now(),
                datetime.now(),
            ))
            
            print(f"   ✅ Produto criado! (ID: {product_id})")
    
    conn.commit()
    
    print("\n" + "="*80)
    print("✅ Todos os produtos foram cadastrados com sucesso!")
    
    # Listar todos os produtos
    print("\n📋 Produtos cadastrados:")
    cursor.execute("""
        SELECT id, name, slug, requires_ui_access, addon_price, is_active, icon
        FROM billing_product
        ORDER BY name;
    """)
    
    products = cursor.fetchall()
    print("-" * 80)
    for product in products:
        product_id, name, slug, requires_ui, addon_price, is_active, icon = product
        status = "🟢 Ativo" if is_active else "🔴 Inativo"
        ui_badge = "🖥️ UI" if requires_ui else "🔌 API"
        price_display = f"R$ {addon_price}" if addon_price else "Incluído"
        print(f"{icon} {name} ({slug})")
        print(f"  {ui_badge} | Addon: {price_display} | Status: {status}")
        print("-" * 80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()

