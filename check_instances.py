"""
Verificar status das instâncias
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("📊 STATUS DAS INSTÂNCIAS:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            wi.friendly_name,
            wi.connection_state,
            wi.health_score,
            wi.msgs_sent_today,
            wi.daily_limit,
            wi.is_active
        FROM notifications_whatsapp_instance wi
        WHERE wi.is_active = true
        ORDER BY wi.friendly_name;
    """)
    
    instances = cursor.fetchall()
    
    for name, state, health, sent_today, daily_limit, active in instances:
        print(f"{name}")
        print(f"   Estado: {state}")
        print(f"   Health: {health}")
        print(f"   Enviadas hoje: {sent_today}")
        print(f"   Limite diário: {daily_limit}")
        print(f"   Ativa: {active}")
        print("-" * 80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERRO: {e}")
