#!/usr/bin/env python
"""
Script para forçar a aplicação de migrations no Railway
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

def force_migrate():
    """Força a aplicação das migrations"""
    print("🚀 Forçando aplicação de migrations...")
    
    # Aplicar migrations específicas
    print("\n📋 Aplicando migrations da app campaigns...")
    execute_from_command_line(['manage.py', 'migrate', 'campaigns'])
    
    # Verificar se foi aplicada
    from django.db import connection
    cursor = connection.cursor()
    
    try:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaigns_campaign' AND column_name = 'last_instance_name'")
        result = cursor.fetchone()
        
        if result:
            print("✅ Campo 'last_instance_name' foi criado com sucesso!")
        else:
            print("❌ Campo 'last_instance_name' ainda não existe")
    except Exception as e:
        print(f"❌ Erro ao verificar campo: {e}")

if __name__ == "__main__":
    force_migrate()
