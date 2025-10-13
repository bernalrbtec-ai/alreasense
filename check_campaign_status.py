"""
Verificar status das campanhas
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("📊 STATUS DAS CAMPANHAS:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            name,
            status,
            messages_sent,
            total_contacts,
            created_at,
            last_message_sent_at
        FROM campaigns_campaign 
        ORDER BY created_at DESC 
        LIMIT 5;
    """)
    
    campaigns = cursor.fetchall()
    
    for name, status, sent, total, created, last_sent in campaigns:
        print(f"{name}")
        print(f"   Status: {status}")
        print(f"   Enviadas: {sent}/{total}")
        created_str = created.strftime("%H:%M:%S") if created else "N/A"
        last_sent_str = last_sent.strftime("%H:%M:%S") if last_sent else "Nunca"
        print(f"   Criada: {created_str}")
        print(f"   Último envio: {last_sent_str}")
        print("-" * 80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ ERRO: {e}")
