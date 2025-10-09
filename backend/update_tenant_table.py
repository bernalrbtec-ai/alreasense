#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def update_tenant_table():
    with connection.cursor() as cursor:
        print("🔧 Atualizando tabela tenancy_tenant...")
        
        # Verificar se coluna plan existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tenancy_tenant' AND column_name = 'plan';
        """)
        has_old_plan = cursor.fetchone() is not None
        
        # Verificar se coluna current_plan_id existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tenancy_tenant' AND column_name = 'current_plan_id';
        """)
        has_current_plan = cursor.fetchone() is not None
        
        # Verificar se coluna ui_access existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tenancy_tenant' AND column_name = 'ui_access';
        """)
        has_ui_access = cursor.fetchone() is not None
        
        # Adicionar coluna current_plan_id se não existir
        if not has_current_plan:
            print("  ➕ Adicionando coluna current_plan_id...")
            cursor.execute("""
                ALTER TABLE tenancy_tenant 
                ADD COLUMN current_plan_id UUID REFERENCES billing_plan(id) ON DELETE SET NULL;
            """)
        else:
            print("  ✅ Coluna current_plan_id já existe")
        
        # Adicionar coluna ui_access se não existir
        if not has_ui_access:
            print("  ➕ Adicionando coluna ui_access...")
            cursor.execute("""
                ALTER TABLE tenancy_tenant 
                ADD COLUMN ui_access BOOLEAN DEFAULT TRUE;
            """)
        else:
            print("  ✅ Coluna ui_access já existe")
        
        # Migrar dados do plano antigo para o novo sistema
        if has_old_plan and has_current_plan:
            print("  🔄 Migrando dados do plano antigo...")
            
            # Buscar IDs dos planos
            cursor.execute("SELECT id, slug FROM billing_plan;")
            plan_ids = {slug: id for id, slug in cursor.fetchall()}
            
            # Mapear planos antigos para novos
            plan_mapping = {
                'starter': plan_ids.get('starter'),
                'pro': plan_ids.get('pro'),
                'api_only': plan_ids.get('api_only'),
                'enterprise': plan_ids.get('enterprise'),
            }
            
            # Atualizar cada tenant
            for old_slug, new_id in plan_mapping.items():
                if new_id:
                    cursor.execute("""
                        UPDATE tenancy_tenant 
                        SET current_plan_id = %s 
                        WHERE plan = %s AND current_plan_id IS NULL;
                    """, (new_id, old_slug))
                    count = cursor.rowcount
                    if count > 0:
                        print(f"    ✅ {count} tenant(s) migrado(s) de '{old_slug}' para novo sistema")
            
            # Remover coluna plan antiga
            print("  ➖ Removendo coluna plan antiga...")
            cursor.execute("ALTER TABLE tenancy_tenant DROP COLUMN IF EXISTS plan;")
        
        print("✅ Tabela tenancy_tenant atualizada com sucesso!")
        
        # Mostrar resumo
        cursor.execute("SELECT COUNT(*) FROM tenancy_tenant;")
        tenant_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM tenancy_tenant 
            WHERE current_plan_id IS NOT NULL;
        """)
        with_plan_count = cursor.fetchone()[0]
        
        print(f"\n📊 Resumo:")
        print(f"  - {tenant_count} tenant(s) no sistema")
        print(f"  - {with_plan_count} tenant(s) com plano configurado")

if __name__ == "__main__":
    update_tenant_table()

