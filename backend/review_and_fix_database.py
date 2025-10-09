#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def review_database():
    with connection.cursor() as cursor:
        print("=" * 80)
        print("🔍 REVISÃO COMPLETA DO BANCO DE DADOS")
        print("=" * 80)
        
        # 1. Verificar tabelas do billing
        print("\n📊 TABELAS DO BILLING:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'billing_%'
            ORDER BY table_name;
        """)
        billing_tables = [t[0] for t in cursor.fetchall()]
        for table in billing_tables:
            print(f"  ✅ {table}")
        
        # 2. Verificar estrutura de cada tabela
        tables_to_check = {
            'billing_product': [
                'id', 'slug', 'name', 'description', 'is_active', 
                'is_addon_available', 'addon_price', 'requires_ui_access',
                'icon', 'color', 'created_at', 'updated_at'
            ],
            'billing_plan': [
                'id', 'slug', 'name', 'description', 'price', 'is_active',
                'sort_order', 'color', 'created_at', 'updated_at'
            ],
            'billing_plan_product': [
                'id', 'plan_id', 'product_id', 'is_included', 
                'limit_value', 'limit_unit', 'is_addon_available', 'created_at'
            ],
            'billing_tenant_product': [
                'id', 'tenant_id', 'product_id', 'is_addon', 'addon_price',
                'api_key', 'is_active', 'activated_at', 'deactivated_at',
                'created_at', 'updated_at'
            ],
            'billing_billinghistory': [
                'id', 'tenant_id', 'action', 'description',
                'old_value', 'new_value', 'old_monthly_total', 'new_monthly_total',
                'created_at', 'created_by_id'
            ]
        }
        
        for table_name, expected_columns in tables_to_check.items():
            print(f"\n📋 {table_name.upper()}:")
            
            # Buscar colunas existentes
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            existing_columns = {col[0]: (col[1], col[2]) for col in cursor.fetchall()}
            
            # Verificar colunas
            missing_columns = []
            for col in expected_columns:
                if col in existing_columns:
                    dtype, nullable = existing_columns[col]
                    print(f"  ✅ {col} ({dtype})")
                else:
                    print(f"  ❌ {col} (FALTANDO)")
                    missing_columns.append(col)
            
            # Colunas extras
            extra_columns = set(existing_columns.keys()) - set(expected_columns)
            if extra_columns:
                print(f"  ⚠️  Colunas extras: {', '.join(extra_columns)}")
            
            if missing_columns:
                print(f"\n  🔧 FALTAM: {', '.join(missing_columns)}")
        
        # 3. Verificar tabela tenancy_tenant
        print("\n📋 TENANCY_TENANT:")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'tenancy_tenant'
            ORDER BY ordinal_position;
        """)
        for col in cursor.fetchall():
            print(f"  - {col[0]} ({col[1]})")
        
        # 4. Contar dados
        print("\n📊 DADOS:")
        for table in billing_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} registros")
        
        print("\n" + "=" * 80)

if __name__ == "__main__":
    review_database()

