#!/usr/bin/env python
"""
Associar produto notifications ao tenant Alrea.ai
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def associate_notifications_to_alrea():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🔔 ASSOCIANDO NOTIFICAÇÕES AO TENANT ALREA.AI")
        print("="*80)
        
        # 1. Buscar tenant Alrea.ai
        cursor.execute("SELECT id, name FROM tenancy_tenant WHERE name = 'Alrea.ai';")
        tenant = cursor.fetchone()
        
        if not tenant:
            print("❌ Tenant Alrea.ai não encontrado")
            return
        
        tenant_id, tenant_name = tenant
        print(f"🏢 Tenant: {tenant_name} (ID: {tenant_id})")
        
        # 2. Buscar produto notifications
        cursor.execute("SELECT id, name, slug FROM billing_product WHERE slug = 'notifications';")
        product = cursor.fetchone()
        
        if not product:
            print("❌ Produto notifications não encontrado")
            return
        
        product_id, product_name, product_slug = product
        print(f"📦 Produto: {product_name} ({product_slug}) (ID: {product_id})")
        
        # 3. Verificar se já existe associação
        cursor.execute("""
            SELECT id, is_active 
            FROM billing_tenant_product 
            WHERE tenant_id = %s AND product_id = %s;
        """, (tenant_id, product_id))
        
        existing = cursor.fetchone()
        
        if existing:
            existing_id, is_active = existing
            if is_active:
                print(f"✅ Associação já existe e está ativa (ID: {existing_id})")
            else:
                # Ativar associação existente
                cursor.execute("""
                    UPDATE billing_tenant_product 
                    SET is_active = true, updated_at = NOW()
                    WHERE id = %s;
                """, (existing_id,))
                print(f"🔄 Associação ativada (ID: {existing_id})")
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
            print(f"➕ Nova associação criada")
        
        # 4. Verificar configuração final
        print(f"\n📊 CONFIGURAÇÃO FINAL DO TENANT:")
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
        
        # 5. Commit das alterações
        conn.commit()
        
        print(f"\n🎉 NOTIFICAÇÕES ASSOCIADAS COM SUCESSO!")
        print("="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    associate_notifications_to_alrea()
