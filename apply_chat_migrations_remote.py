"""
Script para aplicar as tabelas do Chat no Railway
Executa via: railway run python apply_chat_migrations_remote.py
"""
import os
import sys

# Obter DATABASE_URL do ambiente Railway
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL não encontrada. Execute via railway run.")
    sys.exit(1)

print("🚀 Aplicando tabelas do Flow Chat no Railway...")
print("=" * 60)

try:
    import psycopg2
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Ler o SQL do arquivo
    with open('fix_chat_tables.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # Remover comandos psql (\dt)
    sql_commands = []
    for line in sql.split('\n'):
        if not line.strip().startswith('\\'):
            sql_commands.append(line)
    
    clean_sql = '\n'.join(sql_commands)
    
    # Executar
    cursor.execute(clean_sql)
    conn.commit()
    
    print("✅ Tabelas criadas com sucesso!")
    
    # Verificar tabelas
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'chat_%'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    print("\n📋 Tabelas do Chat criadas:")
    for table in tables:
        print(f"   ✓ {table[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 Flow Chat instalado com sucesso no Railway!")
    
except Exception as e:
    print(f"\n❌ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

