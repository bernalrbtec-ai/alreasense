#!/usr/bin/env python
"""
Script para analisar o schema do banco de dados
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def analyze_schema():
    cursor = connection.cursor()
    
    print("🔍 ANALISANDO SCHEMA DO BANCO DE DADOS")
    print("=" * 60)
    
    # 1. Listar todas as tabelas
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
    tables = cursor.fetchall()
    
    print("\n📋 TABELAS NO BANCO:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # 2. Analisar tabela campaigns_log especificamente
    print("\n🔍 ANÁLISE DA TABELA campaigns_log:")
    try:
        cursor.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'campaigns_log' ORDER BY ordinal_position;")
        columns = cursor.fetchall()
        
        print("  Colunas encontradas:")
        for col in columns:
            print(f"    - {col[0]} ({col[1]}) - nullable: {col[2]}")
            
    except Exception as e:
        print(f"  ❌ Erro ao analisar campaigns_log: {e}")
    
    # 3. Verificar se há campo tenant_id em campaigns_log
    print("\n🎯 VERIFICANDO CAMPO tenant_id:")
    try:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaigns_log' AND column_name = 'tenant_id';")
        tenant_id_exists = cursor.fetchone()
        
        if tenant_id_exists:
            print("  ✅ Campo tenant_id EXISTE em campaigns_log")
        else:
            print("  ❌ Campo tenant_id NÃO EXISTE em campaigns_log")
            
    except Exception as e:
        print(f"  ❌ Erro ao verificar tenant_id: {e}")
    
    # 4. Verificar migrations aplicadas
    print("\n📊 MIGRATIONS APLICADAS:")
    try:
        cursor.execute("SELECT app, name, applied FROM django_migrations WHERE app = 'campaigns' ORDER BY applied DESC;")
        migrations = cursor.fetchall()
        
        print("  Migrations da app campaigns:")
        for mig in migrations:
            status = "✅" if mig[2] else "❌"
            print(f"    {status} {mig[0]}.{mig[1]}")
            
    except Exception as e:
        print(f"  ❌ Erro ao verificar migrations: {e}")
    
    # 5. Verificar estrutura da tabela Campaign
    print("\n🔍 ANÁLISE DA TABELA campaigns_campaign:")
    try:
        cursor.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'campaigns_campaign' ORDER BY ordinal_position;")
        columns = cursor.fetchall()
        
        print("  Colunas encontradas:")
        for col in columns:
            print(f"    - {col[0]} ({col[1]}) - nullable: {col[2]}")
            
    except Exception as e:
        print(f"  ❌ Erro ao analisar campaigns_campaign: {e}")

if __name__ == "__main__":
    analyze_schema()
