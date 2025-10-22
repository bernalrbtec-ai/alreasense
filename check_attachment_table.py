"""
Script para verificar estrutura da tabela chat_messageattachment
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, 'backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def check_table():
    with connection.cursor() as cursor:
        # Verificar se tabela existe
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%attachment%'
        """)
        tables = cursor.fetchall()
        print("📋 Tabelas com 'attachment':")
        for table in tables:
            print(f"  - {table[0]}")
        
        print("\n" + "="*60)
        
        # Verificar colunas da tabela
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'chat_messageattachment'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print("\n📊 Colunas de chat_messageattachment:")
        for col in columns:
            print(f"  - {col[0]:30} | {col[1]:20} | NULL={col[2]:5} | DEFAULT={col[3]}")

if __name__ == '__main__':
    check_table()


