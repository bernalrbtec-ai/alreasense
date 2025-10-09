#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def check_billing_history_table():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'billing_billinghistory'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        
        print("Colunas da tabela billing_billinghistory:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]})")

if __name__ == "__main__":
    check_billing_history_table()

