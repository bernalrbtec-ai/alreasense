"""
Verificar erros nos logs
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("🔍 LOGS DE ERRO RECENTES:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            cl.log_type,
            cl.severity,
            cl.message,
            cl.created_at,
            c.name as campaign_name
        FROM campaigns_log cl
        JOIN campaigns_campaign c ON c.id = cl.campaign_id
        WHERE cl.severity IN ('error', 'warning')
        ORDER BY cl.created_at DESC
        LIMIT 10;
    """)
    
    errors = cursor.fetchall()
    
    if errors:
        for log_type, severity, message, created_at, campaign_name in errors:
            time_str = created_at.strftime("%H:%M:%S")
            print(f"{time_str} | {severity.upper()} | {campaign_name} | {log_type}")
            print(f"   {message}")
            print("-" * 80)
    else:
        print("   Nenhum erro encontrado nos logs recentes")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERRO: {e}")
