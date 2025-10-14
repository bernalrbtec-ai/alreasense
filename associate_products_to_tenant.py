#!/usr/bin/env python
"""
Associar produtos ao tenant baseado no plano
"""
import psycopg2
from datetime import datetime

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def associate_products_to_tenant():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🔗 ASSOCIANDO PRODUTOS AO TENANT")
        print("="*80)
        
        # 1. Buscar tenant
        cursor.execute("SELECT id, name FROM tenancy_tenant LIMIT 1;")
        tenant = cursor.fetchone()
        
        if not tenant:
            print("❌ Nenhum tenant encontrado")
            return
        
        tenant_id, tenant_name = tenant
        print(f"🏢 Tenant: {tenant_name} (ID: {tenant_id})")
        
        # 2. Assumir que o tenant tem o plano "flow-pro" (que inclui notificações)
        # Buscar plano flow-pro
        cursor.execute("""
            SELECT id, name, slug FROM billing_plan 
            WHERE slug = 'flow-pro' AND is_active = true;
        """)
        
        plan_info = cursor.fetchone()
        
        if not plan_info:
            print("❌ Plano flow-pro não encontrado")
            return
        
        plan_id, plan_name, plan_slug = plan_info
        print(f"📋 Assumindo plano: {plan_name} ({plan_slug})")
        
        # 3. Buscar produtos do plano
        cursor.execute("""
            SELECT 
                pp.product_id,
                pp.is_included,
                pp.is_addon_available,
                p.slug,
                p.name,
                p.requires_ui_access,
                p.addon_price
            FROM billing_plan_product pp
            JOIN billing_product p ON pp.product_id = p.id
            WHERE pp.plan_id = %s AND pp.is_included = true;
        """, (plan_id,))
        
        plan_products = cursor.fetchall()
        print(f"📦 Produtos incluídos no plano ({len(plan_products)}):")
        
        for product_id, is_included, is_addon_available, slug, name, requires_ui_access, addon_price in plan_products:
            print(f"   - {name} ({slug})")
        
        # 4. Verificar produtos já associados ao tenant
        cursor.execute("""
            SELECT product_id, is_active
            FROM billing_tenant_product
            WHERE tenant_id = %s;
        """, (tenant_id,))
        
        existing_products = {row[0]: row[1] for row in cursor.fetchall()}
        print(f"\n🔍 Produtos já associados: {len(existing_products)}")
        
        # 5. Associar produtos do plano ao tenant
        print(f"\n🔧 ASSOCIANDO PRODUTOS:")
        print("-" * 80)
        
        for product_id, is_included, is_addon_available, slug, name, requires_ui_access, addon_price in plan_products:
            if product_id in existing_products:
                if existing_products[product_id]:
                    print(f"✅ {name}: Já associado e ativo")
                else:
                    # Ativar produto existente
                    cursor.execute("""
                        UPDATE billing_tenant_product
                        SET is_active = true, updated_at = NOW()
                        WHERE tenant_id = %s AND product_id = %s;
                    """, (tenant_id, product_id))
                    print(f"🔄 {name}: Ativado")
            else:
                # Criar nova associação
                cursor.execute("""
                    INSERT INTO billing_tenant_product (
                        tenant_id, product_id, is_active, is_addon, 
                        activated_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, true, false, NOW(), NOW(), NOW()
                    );
                """, (tenant_id, product_id))
                print(f"➕ {name}: Associado")
        
        # 6. Verificar configuração final
        print(f"\n📊 CONFIGURAÇÃO FINAL:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                tp.is_active,
                tp.is_addon,
                tp.activated_at,
                p.slug,
                p.name,
                p.requires_ui_access
            FROM billing_tenant_product tp
            JOIN billing_product p ON tp.product_id = p.id
            WHERE tp.tenant_id = %s
            ORDER BY p.name;
        """, (tenant_id,))
        
        final_products = cursor.fetchall()
        
        for is_active, is_addon, activated_at, slug, name, requires_ui_access in final_products:
            status = "✅ Ativo" if is_active else "❌ Inativo"
            addon_text = " (Addon)" if is_addon else ""
            ui_access = "UI" if requires_ui_access else "API"
            print(f"   {name} ({slug}): {status}{addon_text} - {ui_access}")
        
        # 7. Commit das alterações
        conn.commit()
        
        print(f"\n🎉 PRODUTOS ASSOCIADOS COM SUCESSO!")
        print("="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    associate_products_to_tenant()
