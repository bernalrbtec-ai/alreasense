"""
Lista todas as tabelas do banco Railway.
"""
import psycopg2

DB_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    print("✅ Conectado!\n")
    
    # Listar todas as tabelas
    cursor.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename
    """)
    
    tables = cursor.fetchall()
    
    print(f"📋 TABELAS NO BANCO ({len(tables)}):\n")
    
    for table in tables:
        table_name = table[0]
        
        # Contar registros
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        # Verificar se tem 'instance' no nome
        if 'instance' in table_name.lower() or 'whatsapp' in table_name.lower():
            print(f"🔥 {table_name}: {count} registros")
        else:
            print(f"   {table_name}: {count} registros")
    
    conn.close()

except Exception as e:
    print(f"❌ Erro: {e}")

