#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def check_tables():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'billing_%'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print("Tabelas do billing:")
        for table in tables:
            print(f"  - {table[0]}")
        
        if not tables:
            print("  Nenhuma tabela do billing encontrada")

if __name__ == "__main__":
    check_tables()
