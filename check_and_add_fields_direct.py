#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar e adicionar campos no banco remoto:
1. default_department em notifications_whatsappinstance
2. transfer_message em authn_department
"""
import psycopg2
from urllib.parse import urlparse

# URL do banco remoto (Railway)
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def parse_db_url(url):
    """Parse DATABASE_URL"""
    parsed = urlparse(url)
    return {
        'dbname': parsed.path[1:],
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port
    }

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
    
    db_config = parse_db_url(DATABASE_URL)
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        print(f"Conectado ao banco: {db_config['dbname']} em {db_config['host']}:{db_config['port']}")
        
        # Listar todas as tabelas para verificar nomes
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE '%whatsapp%' OR table_name LIKE '%department%')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print("\nTabelas encontradas:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # 1. Verificar tabela notifications_whatsapp_instance
        table_name = 'notifications_whatsapp_instance'
        print(f"\nVerificando tabela: {table_name}")
        columns = check_table_structure(cursor, table_name)
        print(f"   Colunas existentes: {len(columns)}")
        for col in columns[:5]:  # Mostrar primeiras 5 colunas
            print(f"     - {col[0]} ({col[1]}, nullable={col[2]})")
        
        # Verificar se default_department_id existe
        if check_column_exists(cursor, table_name, 'default_department_id'):
            print("   [OK] Campo 'default_department_id' ja existe")
        else:
            print("   [+] Campo 'default_department_id' NAO existe - adicionando...")
            cursor.execute(f"""
                ALTER TABLE {table_name} 
                ADD COLUMN default_department_id UUID NULL 
                REFERENCES authn_department(id) ON DELETE SET NULL;
            """)
            print("   [OK] Campo 'default_department_id' adicionado")
        
        # Verificar se tem indice
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = %s 
            AND indexname LIKE '%%default_department%%';
        """, (table_name,))
        idx_result = cursor.fetchone()
        if idx_result:
            print("   [OK] Indice para default_department_id ja existe")
        else:
            print("   [+] Criando indice para default_department_id...")
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_whatsappinstance_default_dept 
                ON {table_name}(default_department_id);
            """)
            print("   [OK] Indice criado")
        
        # 2. Verificar tabela authn_department
        print("\nVerificando tabela: authn_department")
        columns = check_table_structure(cursor, 'authn_department')
        print(f"   Colunas existentes: {len(columns)}")
        
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
        if 'conn' in locals():
            conn.rollback()
        print(f"\n[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        print("\nConexao fechada")

if __name__ == '__main__':
    main()

