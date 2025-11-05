#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar e adicionar campos no banco remoto:
1. default_department em notifications_whatsappinstance
2. transfer_message em authn_department
"""
import os
import sys
import django

# Configurar Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection
from django.conf import settings

def get_db_connection():
    """Conecta ao banco remoto usando Django connection"""
    try:
        conn = connection.cursor().connection
        db_config = settings.DATABASES['default']
        print(f"Conectado ao banco: {db_config.get('NAME', 'N/A')} em {db_config.get('HOST', 'N/A')}:{db_config.get('PORT', 'N/A')}")
        return conn
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        return None

def check_column_exists(cursor, table_name, column_name):
    """Verifica se uma coluna existe na tabela"""
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s;
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def check_table_structure(cursor, table_name):
    """Lista todas as colunas de uma tabela"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    return cursor.fetchall()

def main():
    print("="*80)
    print("VERIFICANDO E ADICIONANDO CAMPOS NO BANCO REMOTO")
    print("="*80)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = connection.cursor()
        
        # 1. Verificar tabela notifications_whatsappinstance
        print("\n📋 Verificando tabela: notifications_whatsappinstance")
        columns = check_table_structure(cursor, 'notifications_whatsappinstance')
        print(f"   Colunas existentes: {len(columns)}")
        for col in columns:
            print(f"     - {col[0]} ({col[1]}, nullable={col[2]})")
        
        # Verificar se default_department_id existe
        if check_column_exists(cursor, 'notifications_whatsappinstance', 'default_department_id'):
            print("   [OK] Campo 'default_department_id' ja existe")
        else:
            print("   [+] Campo 'default_department_id' NAO existe - adicionando...")
            cursor.execute("""
                ALTER TABLE notifications_whatsappinstance 
                ADD COLUMN default_department_id UUID NULL 
                REFERENCES authn_department(id) ON DELETE SET NULL;
            """)
            print("   [OK] Campo 'default_department_id' adicionado")
        
        # Verificar se tem indice
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'notifications_whatsappinstance' 
            AND indexname LIKE '%default_department%';
        """)
        if cursor.fetchone():
            print("   [OK] Indice para default_department_id ja existe")
        else:
            print("   [+] Criando indice para default_department_id...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whatsappinstance_default_dept 
                ON notifications_whatsappinstance(default_department_id);
            """)
            print("   [OK] Indice criado")
        
        # 2. Verificar tabela authn_department
        print("\nVerificando tabela: authn_department")
        columns = check_table_structure(cursor, 'authn_department')
        print(f"   Colunas existentes: {len(columns)}")
        for col in columns:
            print(f"     - {col[0]} ({col[1]}, nullable={col[2]})")
        
        # Verificar se transfer_message existe
        if check_column_exists(cursor, 'authn_department', 'transfer_message'):
            print("   [OK] Campo 'transfer_message' ja existe")
        else:
            print("   [+] Campo 'transfer_message' NAO existe - adicionando...")
            cursor.execute("""
                ALTER TABLE authn_department 
                ADD COLUMN transfer_message TEXT NULL;
            """)
            print("   [OK] Campo 'transfer_message' adicionado")
        
        # Commit das alteracoes
        conn.commit()
        print("\n[OK] Todas as alteracoes foram aplicadas com sucesso!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        print("\nConexao fechada")

if __name__ == '__main__':
    main()

