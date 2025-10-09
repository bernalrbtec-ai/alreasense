#!/usr/bin/env python
"""
Setup completo do banco do zero
Roda diretamente sem Django para evitar problemas de import
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import time

DB_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'alrea_sense_local'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'db'),
    'port': os.getenv('DB_PORT', '5432')
}

print("🔥 FRESH SETUP - Resetando banco de dados...")
print("=" * 60)

# Conectar e dropar/recriar banco
try:
    # Conectar ao postgres (não ao banco específico)
    conn = psycopg2.connect(
        dbname='postgres',
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port']
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    print(f"\n1️⃣ Dropando banco '{DB_CONFIG['dbname']}'...")
    cursor.execute(f"DROP DATABASE IF EXISTS {DB_CONFIG['dbname']};")
    print("   ✓ Banco dropado")
    
    print(f"\n2️⃣ Criando banco '{DB_CONFIG['dbname']}'...")
    cursor.execute(f"CREATE DATABASE {DB_CONFIG['dbname']};")
    print("   ✓ Banco criado")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Banco de dados resetado com sucesso!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Erro: {e}")
    exit(1)

