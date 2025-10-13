"""
🧹 LIMPEZA DE LOGS DO RAILWAY
Script para limpar logs antigos e facilitar debug dos workers
"""
import psycopg2
from datetime import datetime, timedelta
from django.utils import timezone

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def clear_campaign_logs():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🧹 LIMPEZA DE LOGS DE CAMPANHAS")
        print("="*80)
        
        # 1. Verificar logs atuais
        print("\n📊 LOGS ATUAIS:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                cl.id,
                cl.log_type,
                cl.severity,
                cl.message,
                cl.created_at,
                c.name as campaign_name
            FROM campaigns_log cl
            JOIN campaigns_campaign c ON c.id = cl.campaign_id
            ORDER BY cl.created_at DESC
            LIMIT 20;
        """)
        
        current_logs = cursor.fetchall()
        
        if current_logs:
            print("🔍 Últimos 20 logs:")
            for log_id, log_type, severity, message, created_at, campaign_name in current_logs:
                print(f"   {created_at.strftime('%H:%M:%S')} | {severity.upper()} | {campaign_name} | {log_type} | {message[:60]}...")
        else:
            print("   Nenhum log encontrado")
        
        # 2. Contar logs por tipo
        print("\n📈 ESTATÍSTICAS DOS LOGS:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                log_type,
                severity,
                COUNT(*) as count
            FROM campaigns_log
            GROUP BY log_type, severity
            ORDER BY count DESC;
        """)
        
        stats = cursor.fetchall()
        
        for log_type, severity, count in stats:
            print(f"   {log_type} ({severity}): {count} logs")
        
        # 3. Limpar logs antigos (mais de 1 hora)
        print("\n🧹 LIMPEZA DE LOGS ANTIGOS:")
        print("-" * 80)
        
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        cursor.execute("""
            DELETE FROM campaigns_log 
            WHERE created_at < %s 
            AND severity IN ('info', 'debug');
        """, (cutoff_time,))
        
        deleted_count = cursor.rowcount
        
        print(f"✅ {deleted_count} logs antigos removidos (mais de 1 hora)")
        
        # 4. Manter apenas logs importantes recentes
        print("\n🎯 MANTENDO LOGS IMPORTANTES:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT COUNT(*) FROM campaigns_log 
            WHERE severity IN ('error', 'warning')
            AND created_at >= %s;
        """, (cutoff_time,))
        
        important_logs = cursor.fetchone()[0]
        
        print(f"   Logs de erro/warning mantidos: {important_logs}")
        
        # 5. Verificar logs após limpeza
        cursor.execute("SELECT COUNT(*) FROM campaigns_log;")
        total_remaining = cursor.fetchone()[0]
        
        print(f"   Total de logs restantes: {total_remaining}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✅ LIMPEZA CONCLUÍDA!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

def clear_worker_debug_logs():
    """Limpar logs específicos de debug dos workers"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("\n🔧 LIMPEZA DE LOGS DE DEBUG DOS WORKERS:")
        print("-" * 80)
        
        # Limpar logs de debug muito verbosos
        cursor.execute("""
            DELETE FROM campaigns_log 
            WHERE (message LIKE '%Worker%' 
            OR message LIKE '%DEBUG%'
            OR message LIKE '%Processando Campanha%'
            OR message LIKE '%Lote processado%')
            AND created_at < %s;
        """, (timezone.now() - timedelta(minutes=30),))
        
        debug_deleted = cursor.rowcount
        
        print(f"✅ {debug_deleted} logs de debug removidos")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro na limpeza de debug: {e}")

if __name__ == '__main__':
    clear_campaign_logs()
    clear_worker_debug_logs()
