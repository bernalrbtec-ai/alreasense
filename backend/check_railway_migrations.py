#!/usr/bin/env python
"""
Script para verificar se as migrations estão sendo aplicadas no Railway
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

def check_migrations():
    """Verifica o status das migrations"""
    print("🔍 Verificando migrations no Railway...")
    
    # Verificar migrations pendentes
    print("\n📋 Migrations pendentes:")
    execute_from_command_line(['manage.py', 'showmigrations', 'campaigns'])
    
    # Verificar se o campo last_instance_name existe
    from django.db import connection
    cursor = connection.cursor()
    
    try:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaigns_campaign' AND column_name = 'last_instance_name'")
        result = cursor.fetchone()
        
        if result:
            print("✅ Campo 'last_instance_name' existe na tabela 'campaigns_campaign'")
        else:
            print("❌ Campo 'last_instance_name' NÃO existe na tabela 'campaigns_campaign'")
            print("   Isso significa que a migration não foi aplicada no Railway")
    except Exception as e:
        print(f"❌ Erro ao verificar campo: {e}")
    
    # Verificar estrutura da tabela campaigns_campaign
    print("\n📊 Estrutura da tabela campaigns_campaign:")
    try:
        cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'campaigns_campaign' ORDER BY ordinal_position")
        columns = cursor.fetchall()
        
        for col_name, col_type in columns:
            if 'instance' in col_name.lower() or 'contact' in col_name.lower():
                print(f"   {col_name}: {col_type}")
    except Exception as e:
        print(f"❌ Erro ao verificar estrutura: {e}")

if __name__ == "__main__":
    check_migrations()
