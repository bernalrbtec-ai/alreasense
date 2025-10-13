"""
Encontrar tabelas relacionadas a instâncias
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE '%instance%' 
        OR table_name LIKE '%whatsapp%'
        OR table_name LIKE '%notification%'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    
    print("📋 TABELAS ENCONTRADAS:")
    for table in tables:
        print(f"  - {table[0]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERRO: {e}")
