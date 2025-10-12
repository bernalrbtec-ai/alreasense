#!/usr/bin/env python
"""
Script para marcar migrations como aplicadas (fake) quando as tabelas já existem
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.core.management import call_command
from django.db import connection

print("🔧 Verificando e corrigindo migrations...")

with connection.cursor() as cursor:
    # Verifica se a tabela authn_user existe
    cursor.execute("""
        SELECT tablename FROM pg_tables 
        WHERE tablename='authn_user';
    """)
    user_table_exists = cursor.fetchone()
    
    # Verifica se a tabela billing_tenant_product existe
    cursor.execute("""
        SELECT tablename FROM pg_tables 
        WHERE tablename='billing_tenant_product';
    """)
    billing_table_exists = cursor.fetchone()

if user_table_exists:
    print("✅ Tabela authn_user já existe, marcando migrations como fake...")
    call_command('migrate', 'authn', '0002_initial', fake=True, verbosity=0)
    
if billing_table_exists:
    print("✅ Tabelas de billing já existem, marcando migrations como fake...")
    call_command('migrate', 'billing', fake=True, verbosity=0)

# Agora roda as migrations normalmente
print("🚀 Aplicando demais migrations...")
call_command('migrate', verbosity=1)

print("\n✅ Migrations aplicadas com sucesso!")



