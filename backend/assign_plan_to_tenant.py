#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection
import uuid

def assign_plan_to_tenant():
    with connection.cursor() as cursor:
        print("🎯 Atribuindo plano Starter ao tenant existente...")
        
        # Buscar tenant
        cursor.execute("SELECT id, name FROM tenancy_tenant LIMIT 1;")
        tenant = cursor.fetchone()
        
        if not tenant:
            print("❌ Nenhum tenant encontrado!")
            return
        
        tenant_id, tenant_name = tenant
        print(f"  📋 Tenant: {tenant_name} ({tenant_id})")
        
        # Buscar plano Starter
        cursor.execute("SELECT id FROM billing_plan WHERE slug = 'starter';")
        starter_plan = cursor.fetchone()
        
        if not starter_plan:
            print("❌ Plano Starter não encontrado!")
            return
        
        starter_plan_id = starter_plan[0]
        print(f"  💳 Plano Starter: {starter_plan_id}")
        
        # Atribuir plano ao tenant
        cursor.execute("""
            UPDATE tenancy_tenant 
            SET current_plan_id = %s 
            WHERE id = %s;
        """, (starter_plan_id, tenant_id))
        print("  ✅ Plano atribuído ao tenant")
        
        # Buscar produtos do plano Starter
        cursor.execute("""
            SELECT pp.product_id, p.name, pp.limit_value, pp.limit_unit
            FROM billing_plan_product pp
            JOIN billing_product p ON pp.product_id = p.id
            WHERE pp.plan_id = %s AND pp.is_included = TRUE;
        """, (starter_plan_id,))
        plan_products = cursor.fetchall()
        
        print(f"\n  📦 Ativando {len(plan_products)} produto(s) do plano:")
        
        # Ativar produtos para o tenant
        for product_id, product_name, limit_value, limit_unit in plan_products:
            # Verificar se já existe
            cursor.execute("""
                SELECT id FROM billing_tenant_product 
                WHERE tenant_id = %s AND product_id = %s;
            """, (tenant_id, product_id))
            
            if cursor.fetchone():
                print(f"    ⏭️  {product_name} já ativado")
                continue
            
            # Criar tenant_product
            cursor.execute("""
                INSERT INTO billing_tenant_product 
                (id, tenant_id, product_id, is_addon, is_active, 
                 activated_at, created_at, updated_at)
                VALUES (%s, %s, %s, FALSE, TRUE, NOW(), NOW(), NOW());
            """, (str(uuid.uuid4()), tenant_id, product_id))
            
            print(f"    ✅ {product_name} ativado (limite: {limit_value} {limit_unit})")
        
        print("\n✅ Configuração concluída!")
        
        # Mostrar resumo
        cursor.execute("""
            SELECT p.name, tp.is_addon, tp.is_active
            FROM billing_tenant_product tp
            JOIN billing_product p ON tp.product_id = p.id
            WHERE tp.tenant_id = %s;
        """, (tenant_id,))
        
        products = cursor.fetchall()
        
        print(f"\n📊 Resumo do Tenant '{tenant_name}':")
        print(f"  💳 Plano: Starter (R$ 49/mês)")
        print(f"  📦 Produtos ativos:")
        for name, is_addon, is_active in products:
            status = "✅" if is_active else "❌"
            addon_label = " (Add-on)" if is_addon else ""
            print(f"    {status} {name}{addon_label}")

if __name__ == "__main__":
    assign_plan_to_tenant()

