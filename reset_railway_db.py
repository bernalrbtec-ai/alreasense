#!/usr/bin/env python
"""
Script para zerar o banco de dados PostgreSQL na Railway
"""
import psycopg2

# Credenciais do PostgreSQL
username = 'postgres'
password = 'wDxByyoBGIzFwodHccWSkeLmqCcuwpVt'
database = 'railway'
hostname = 'postgres-59a0986d.railway.internal'
port = 5432

print(f"🔌 Conectando ao banco: {database} em {hostname}")

try:
    # Conecta ao banco postgres padrão primeiro
    conn = psycopg2.connect(
        dbname='postgres',
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    print(f"🗑️  Dropando banco de dados: {database}")
    
    # Termina todas as conexões ativas
    cursor.execute(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{database}'
        AND pid <> pg_backend_pid();
    """)
    
    # Drop database
    cursor.execute(f"DROP DATABASE IF EXISTS {database};")
    print(f"✅ Banco {database} deletado")
    
    # Recria database
    cursor.execute(f"CREATE DATABASE {database};")
    print(f"✅ Banco {database} recriado")
    
    cursor.close()
    conn.close()
    
    # Conecta ao banco recriado para instalar extensões
    conn = psycopg2.connect(
        dbname=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Instala extensões necessárias
    print("📦 Instalando extensões...")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gin;")
    print("✅ Extensões instaladas")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ BANCO DE DADOS ZERADO COM SUCESSO!")
    print("="*70)
    print("\n📋 Próximos passos:")
    print("1. Fazer deploy: railway up")
    print("2. As migrations serão aplicadas automaticamente")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
