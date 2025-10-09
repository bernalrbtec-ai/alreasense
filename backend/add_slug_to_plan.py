#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def add_slug_to_plan():
    with connection.cursor() as cursor:
        # Adicionar coluna slug se não existir
        cursor.execute("""
            ALTER TABLE billing_plan 
            ADD COLUMN IF NOT EXISTS slug VARCHAR(50);
        """)
        
        # Adicionar coluna sort_order se não existir
        cursor.execute("""
            ALTER TABLE billing_plan 
            ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;
        """)
        
        print("✅ Colunas adicionadas à tabela billing_plan!")

if __name__ == "__main__":
    add_slug_to_plan()
