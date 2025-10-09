#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def align_database():
    with connection.cursor() as cursor:
        print("🔧 Alinhando banco de dados com modelos...")
        
        # 1. Adicionar colunas faltantes em billing_product
        print("\n📦 Atualizando billing_product...")
        cursor.execute("""
            ALTER TABLE billing_product 
            ADD COLUMN IF NOT EXISTS icon VARCHAR(50) DEFAULT '📦';
        """)
        cursor.execute("""
            ALTER TABLE billing_product 
            ADD COLUMN IF NOT EXISTS color VARCHAR(7) DEFAULT '#3B82F6';
        """)
        print("  ✅ Colunas icon e color adicionadas")
        
        # 2. Adicionar colunas faltantes em billing_plan
        print("\n💳 Atualizando billing_plan...")
        cursor.execute("""
            ALTER TABLE billing_plan 
            ADD COLUMN IF NOT EXISTS color VARCHAR(7) DEFAULT '#3B82F6';
        """)
        print("  ✅ Coluna color adicionada")
        
        # 3. Adicionar colunas faltantes em billing_plan_product
        print("\n🔗 Atualizando billing_plan_product...")
        cursor.execute("""
            ALTER TABLE billing_plan_product 
            ADD COLUMN IF NOT EXISTS is_addon_available BOOLEAN DEFAULT TRUE;
        """)
        cursor.execute("""
            ALTER TABLE billing_plan_product 
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """)
        print("  ✅ Colunas is_addon_available e created_at adicionadas")
        
        # 4. Renomear billing_billinghistory para billing_history
        print("\n📊 Verificando billing_history...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'billing_history';
        """)
        has_billing_history = cursor.fetchone() is not None
        
        if not has_billing_history:
            print("  🔄 Renomeando billing_billinghistory para billing_history...")
            cursor.execute("""
                ALTER TABLE billing_billinghistory RENAME TO billing_history;
            """)
            print("  ✅ Tabela renomeada")
        else:
            print("  ✅ Tabela billing_history já existe")
        
        # 5. Adicionar colunas faltantes em billing_tenant_product
        print("\n🏢 Atualizando billing_tenant_product...")
        cursor.execute("""
            ALTER TABLE billing_tenant_product 
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """)
        cursor.execute("""
            ALTER TABLE billing_tenant_product 
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """)
        print("  ✅ Colunas created_at e updated_at adicionadas")
        
        print("\n✅ Banco de dados alinhado com os modelos!")
        
        # Mostrar resumo
        print("\n📊 RESUMO DAS TABELAS:")
        tables = [
            'billing_product',
            'billing_plan',
            'billing_plan_product',
            'billing_tenant_product',
            'billing_history'
        ]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = %s;
            """, (table,))
            col_count = cursor.fetchone()[0]
            
            print(f"  ✅ {table}: {count} registros, {col_count} colunas")

if __name__ == "__main__":
    align_database()

