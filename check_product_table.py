#!/usr/bin/env python
"""
Verificar estrutura da tabela billing_product
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Colunas da tabela billing_product:")
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'billing_product' 
        ORDER BY ordinal_position;
    """)
    
    columns = cursor.fetchall()
    for col, dtype in columns:
        print(f"  {col}: {dtype}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()
