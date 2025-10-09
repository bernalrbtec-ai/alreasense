#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def create_billing_tables():
    with connection.cursor() as cursor:
        # Criar tabela Product
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_product (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                slug VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_addon_available BOOLEAN DEFAULT FALSE,
                addon_price DECIMAL(10,2),
                requires_ui_access BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Criar tabela PlanProduct
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_plan_product (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                plan_id UUID NOT NULL REFERENCES billing_plan(id) ON DELETE CASCADE,
                product_id UUID NOT NULL REFERENCES billing_product(id) ON DELETE CASCADE,
                is_included BOOLEAN DEFAULT TRUE,
                limit_value INTEGER,
                limit_unit VARCHAR(50),
                UNIQUE(plan_id, product_id)
            );
        """)
        
        # Criar tabela TenantProduct
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
                UNIQUE(tenant_id, product_id)
            );
        """)
        
        # Criar tabela BillingHistory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_billinghistory (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
                action VARCHAR(50) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        print("✅ Tabelas do billing criadas com sucesso!")

if __name__ == "__main__":
    create_billing_tables()
