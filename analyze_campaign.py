#!/usr/bin/env python3
import psycopg2
import json
from datetime import datetime

def analyze_campaign():
    # Conectar ao banco Railway
    conn = psycopg2.connect(
        host='roundhouse.proxy.rlwy.net',
        port='5432',
        database='railway',
        user='postgres',
        password='aBcDfGhIjKlMnOpQrStUvWxYz123456'
    )

    cur = conn.cursor()

    try:
        # Buscar a campanha específica
        cur.execute("""
        SELECT id, name, status, created_at, updated_at, 
               interval_min, interval_max, daily_limit_per_instance, pause_on_health_below,
               next_message_scheduled_at, total_contacts, messages_sent, messages_delivered
        FROM campaigns_campaign 
        WHERE name LIKE '%contatos_parte32_divisao_3_30contatos%'
        ORDER BY created_at DESC
        LIMIT 1
        """)

        campaign = cur.fetchone()
        if not campaign:
            print("❌ Campanha não encontrada!")
            return

        print("=== CAMPANHA ENCONTRADA ===")
        print(f"ID: {campaign[0]}")
        print(f"Nome: {campaign[1]}")
        print(f"Status: {campaign[2]}")
        print(f"Criada: {campaign[3]}")
        print(f"Atualizada: {campaign[4]}")
        print(f"Intervalo: {campaign[5]}-{campaign[6]}s")
        print(f"Limite diário: {campaign[7]}")
        print(f"Health mínimo: {campaign[8]}")
        print(f"Próximo envio: {campaign[9]}")
        print(f"Total contatos: {campaign[10]}")
        print(f"Mensagens enviadas: {campaign[11]}")
        print(f"Mensagens entregues: {campaign[12]}")
        
        campaign_id = campaign[0]
        
        # Buscar logs recentes da campanha
        print("\n=== LOGS RECENTES (últimos 30) ===")
        cur.execute("""
        SELECT created_at, log_type, severity, message, details
        FROM campaigns_campaignlog 
        WHERE campaign_id = %s
        ORDER BY created_at DESC
        LIMIT 30
        """, (campaign_id,))
        
        logs = cur.fetchall()
        for log in logs:
            print(f"{log[0]} | {log[1]} | {log[2]} | {log[3]}")
            if log[4]:
                try:
                    details = json.loads(log[4]) if isinstance(log[4], str) else log[4]
                    if details:
                        print(f"  Detalhes: {details}")
                except:
                    print(f"  Detalhes: {log[4]}")
            print()
        
        # Verificar instâncias da campanha
        print("=== INSTÂNCIAS DA CAMPANHA ===")
        cur.execute("""
        SELECT wi.friendly_name, wi.phone_number, wi.health_score, wi.msgs_sent_today, wi.is_active
        FROM campaigns_campaign_instances ci
        JOIN notifications_whatsappinstance wi ON ci.whatsappinstance_id = wi.id
        WHERE ci.campaign_id = %s
        """, (campaign_id,))
        
        instances = cur.fetchall()
        for instance in instances:
            print(f"Instância: {instance[0]} | {instance[1]} | Health: {instance[2]} | Enviadas hoje: {instance[3]} | Ativa: {instance[4]}")
        
        # Verificar contatos pendentes
        print("\n=== CONTATOS PENDENTES ===")
        cur.execute("""
        SELECT COUNT(*) as total_pending
        FROM campaigns_campaigncontact 
        WHERE campaign_id = %s AND status = 'pending'
        """, (campaign_id,))
        
        pending = cur.fetchone()
        print(f"Contatos pendentes: {pending[0]}")
        
        # Verificar contatos por status
        print("\n=== CONTATOS POR STATUS ===")
        cur.execute("""
        SELECT status, COUNT(*) as count
        FROM campaigns_campaigncontact 
        WHERE campaign_id = %s
        GROUP BY status
        ORDER BY status
        """, (campaign_id,))
        
        status_counts = cur.fetchall()
        for status, count in status_counts:
            print(f"{status}: {count}")
            
        # Verificar se há logs de erro ou problemas
        print("\n=== LOGS DE ERRO/PROBLEMA ===")
        cur.execute("""
        SELECT created_at, log_type, severity, message, details
        FROM campaigns_campaignlog 
        WHERE campaign_id = %s 
        AND (severity = 'error' OR severity = 'warning' OR log_type LIKE '%fail%' OR log_type LIKE '%error%')
        ORDER BY created_at DESC
        LIMIT 10
        """, (campaign_id,))
        
        error_logs = cur.fetchall()
        if error_logs:
            for log in error_logs:
                print(f"🚨 {log[0]} | {log[1]} | {log[2]} | {log[3]}")
                if log[4]:
                    try:
                        details = json.loads(log[4]) if isinstance(log[4], str) else log[4]
                        if details:
                            print(f"  Detalhes: {details}")
                    except:
                        print(f"  Detalhes: {log[4]}")
                print()
        else:
            print("✅ Nenhum log de erro encontrado")
            
        # Verificar logs de instância não disponível
        print("\n=== LOGS DE INSTÂNCIA NÃO DISPONÍVEL ===")
        cur.execute("""
        SELECT created_at, log_type, severity, message, details
        FROM campaigns_campaignlog 
        WHERE campaign_id = %s 
        AND (message LIKE '%instância%' OR message LIKE '%disponível%' OR message LIKE '%instance%')
        ORDER BY created_at DESC
        LIMIT 10
        """, (campaign_id,))
        
        instance_logs = cur.fetchall()
        if instance_logs:
            for log in instance_logs:
                print(f"📱 {log[0]} | {log[1]} | {log[2]} | {log[3]}")
                if log[4]:
                    try:
                        details = json.loads(log[4]) if isinstance(log[4], str) else log[4]
                        if details:
                            print(f"  Detalhes: {details}")
                    except:
                        print(f"  Detalhes: {log[4]}")
                print()
        else:
            print("✅ Nenhum log de problema de instância encontrado")

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    analyze_campaign()
