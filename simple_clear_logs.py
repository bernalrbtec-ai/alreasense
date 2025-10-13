"""
🧹 LIMPEZA SIMPLES DE LOGS
"""
import psycopg2
from datetime import datetime, timedelta

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def clear_logs():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🧹 LIMPEZA SIMPLES DE LOGS")
        print("="*80)
        
        # 1. Ver logs atuais
        print("\n📊 LOGS ATUAIS:")
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
            ORDER BY cl.created_at DESC
            LIMIT 10;
        """)
        
        current_logs = cursor.fetchall()
        
        for log_type, severity, message, created_at, campaign_name in current_logs:
            print(f"   {created_at.strftime('%H:%M:%S')} | {severity.upper()} | {campaign_name} | {log_type} | {message[:50]}...")
        
        # 2. Limpar logs antigos (usando SQL direto)
        print("\n🧹 LIMPANDO LOGS ANTIGOS:")
        print("-" * 80)
        
        # Limpar logs de mais de 30 minutos
        cursor.execute("""
            DELETE FROM campaigns_log 
            WHERE created_at < NOW() - INTERVAL '30 minutes'
            AND severity IN ('info', 'debug');
        """)
        
        deleted_count = cursor.rowcount
        print(f"✅ {deleted_count} logs antigos removidos")
        
        # 3. Verificar logs restantes
        cursor.execute("SELECT COUNT(*) FROM campaigns_log;")
        total_remaining = cursor.fetchone()[0]
        print(f"📊 Total de logs restantes: {total_remaining}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✅ LIMPEZA CONCLUÍDA!")
        print("="*80)
        
    except Exception as e:
        print(f"❌ ERRO: {e}")

if __name__ == '__main__':
    clear_logs()
