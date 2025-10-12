#!/usr/bin/env python
"""
Script para zerar o banco de dados PostgreSQL na Railway via URL pública
"""
import psycopg2

# Credenciais do PostgreSQL (URL pública)
username = 'postgres'
password = 'wDxByyoBGIzFwodHccWSkeLmqCcuwpVt'
database = 'railway'
hostname = 'caboose.proxy.rlwy.net'
port = 25280

print(f"🔌 Conectando ao banco: {database} em {hostname}:{port}")

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
    print(f"🔌 Reconectando ao banco recriado...")
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
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("  ✅ vector")
    except Exception as e:
        print(f"  ⚠️  vector (não disponível): {e}")
    
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        print("  ✅ pg_trgm")
    except Exception as e:
        print(f"  ⚠️  pg_trgm: {e}")
    
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gin;")
        print("  ✅ btree_gin")
    except Exception as e:
        print(f"  ⚠️  btree_gin: {e}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ BANCO DE DADOS ZERADO COM SUCESSO!")
    print("="*70)
    print("\n📋 Próximos passos:")
    print("1. Fazer deploy: railway up")
    print("2. As migrations serão aplicadas automaticamente do zero")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
    exit(1)


