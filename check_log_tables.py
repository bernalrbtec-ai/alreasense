"""
Verificar tabelas de log no Railway
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Verificar tabelas que contêm 'log'
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE '%log%' 
        ORDER BY table_name;
    """)
    
    log_tables = cursor.fetchall()
    
    print("📋 TABELAS DE LOG ENCONTRADAS:")
    for table in log_tables:
        print(f"  - {table[0]}")
    
    # Verificar tabelas de campanha
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE '%campaign%' 
        ORDER BY table_name;
    """)
    
    campaign_tables = cursor.fetchall()
    
    print("\n📋 TABELAS DE CAMPANHA ENCONTRADAS:")
    for table in campaign_tables:
        print(f"  - {table[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERRO: {e}")
