#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def fix_billing_tables():
    with connection.cursor() as cursor:
        # Deletar tabelas existentes com nomes incorretos
        cursor.execute("DROP TABLE IF EXISTS billing_planproduct CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS billing_tenantproduct CASCADE;")
        
        # Criar tabela PlanProduct com nome correto
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_plan_product (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                plan_id UUID NOT NULL REFERENCES billing_plan(id) ON DELETE CASCADE,
                product_id UUID NOT NULL REFERENCES billing_product(id) ON DELETE CASCADE,
                is_included BOOLEAN DEFAULT TRUE,
                limit_value INTEGER,
                limit_unit VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(plan_id, product_id)
            );
        """)
        
        # Criar tabela TenantProduct com nome correto
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_tenant_product (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                product_id UUID NOT NULL REFERENCES billing_product(id) ON DELETE CASCADE,
                is_addon BOOLEAN DEFAULT FALSE,
                addon_price DECIMAL(10,2),
                api_key VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                activated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deactivated_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(tenant_id, product_id)
            );
        """)
        
        print("✅ Tabelas do billing corrigidas com sucesso!")

if __name__ == "__main__":
    fix_billing_tables()
