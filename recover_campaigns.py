"""
🔧 RECOVERY DE CAMPANHAS
Detecta e corrige campanhas travadas após deploy ou falha
"""
import psycopg2
from datetime import datetime, timedelta

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def recover_campaigns():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🔧 RECOVERY DE CAMPANHAS")
        print("="*80)
        
        # 1. Detectar campanhas travadas (running mas sem atividade recente)
        print("\n🔍 Detectando campanhas travadas...")
        
        cursor.execute("""
            SELECT 
                id, name, status, messages_sent, total_contacts,
                last_message_sent_at, updated_at
            FROM campaigns_campaign
            WHERE status = 'running'
            ORDER BY updated_at DESC;
        """)
        
        running_campaigns = cursor.fetchall()
        
        if not running_campaigns:
            print("✅ Nenhuma campanha em execução.")
        else:
            print(f"\n📊 {len(running_campaigns)} campanha(s) em execução:\n")
            print("-" * 80)
            
            stuck_campaigns = []
            healthy_campaigns = []
            
            for campaign in running_campaigns:
                campaign_id, name, status, messages_sent, total_contacts, last_message_at, updated_at = campaign
                
                # Considerar travada se não enviou mensagem há mais de 5 minutos
                is_stuck = False
                if last_message_at:
                    time_since_last = datetime.now(last_message_at.tzinfo) - last_message_at
                    if time_since_last > timedelta(minutes=5):
                        is_stuck = True
                else:
                    # Nunca enviou mensagem
                    time_since_created = datetime.now(updated_at.tzinfo) - updated_at
                    if time_since_created > timedelta(minutes=2):
                        is_stuck = True
                
                progress = (messages_sent / total_contacts * 100) if total_contacts > 0 else 0
                
                status_icon = "⚠️" if is_stuck else "✅"
                status_text = "TRAVADA" if is_stuck else "OK"
                
                print(f"{status_icon} {name}")
                print(f"   Status: {status_text}")
                print(f"   Progresso: {messages_sent}/{total_contacts} ({progress:.1f}%)")
                if last_message_at:
                    print(f"   Última mensagem: {last_message_at.strftime('%H:%M:%S')}")
                else:
                    print(f"   Última mensagem: Nunca")
                print("-" * 80)
                
                if is_stuck:
                    stuck_campaigns.append((campaign_id, name, messages_sent, total_contacts))
                else:
                    healthy_campaigns.append((campaign_id, name))
        
        # 2. Listar campanhas pausadas
        print("\n🔍 Campanhas pausadas:\n")
        
        cursor.execute("""
            SELECT 
                id, name, messages_sent, total_contacts, updated_at
            FROM campaigns_campaign
            WHERE status = 'paused'
            ORDER BY updated_at DESC
            LIMIT 10;
        """)
        
        paused_campaigns = cursor.fetchall()
        
        if not paused_campaigns:
            print("✅ Nenhuma campanha pausada.")
        else:
            print(f"📊 {len(paused_campaigns)} campanha(s) pausada(s):\n")
            print("-" * 80)
            
            for campaign_id, name, messages_sent, total_contacts, updated_at in paused_campaigns:
                progress = (messages_sent / total_contacts * 100) if total_contacts > 0 else 0
                print(f"⏸️  {name}")
                print(f"   ID: {campaign_id}")
                print(f"   Progresso: {messages_sent}/{total_contacts} ({progress:.1f}%)")
                print(f"   Pausada em: {updated_at.strftime('%d/%m/%Y %H:%M:%S')}")
                print("-" * 80)
        
        # 3. Oferecer ações
        print("\n" + "="*80)
        print("🔧 AÇÕES DISPONÍVEIS:")
        print("="*80)
        print("\n1. Pausar campanhas travadas")
        print("2. Retomar todas as campanhas pausadas")
        print("3. Retomar campanha específica")
        print("4. Ver logs de uma campanha")
        print("5. Sair")
        
        action = input("\nEscolha uma ação (1-5): ").strip()
        
        if action == '1' and stuck_campaigns:
            print(f"\n🛑 Pausando {len(stuck_campaigns)} campanha(s) travada(s)...")
            
            for campaign_id, name, _, _ in stuck_campaigns:
                cursor.execute("""
                    UPDATE campaigns_campaign
                    SET status = 'paused', updated_at = %s
                    WHERE id = %s;
                """, (datetime.now(), campaign_id))
                
                # Log
                cursor.execute("""
                    INSERT INTO campaigns_campaignlog (
                        id, campaign_id, log_type, severity, message,
                        details, created_at
                    )
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s);
                """, (
                    campaign_id,
                    'paused',
                    'warning',
                    f'Campanha pausada automaticamente (travada)',
                    '{"reason": "stuck_campaign", "auto_paused": true}',
                    datetime.now()
                ))
                
                print(f"   ✓ {name}")
            
            conn.commit()
            print("\n✅ Campanhas pausadas com sucesso!")
        
        elif action == '2' and paused_campaigns:
            confirm = input(f"\n⚠️  Confirma retomar {len(paused_campaigns)} campanha(s)? (SIM/não): ")
            
            if confirm.upper() == 'SIM':
                print(f"\n▶️  Retomando {len(paused_campaigns)} campanha(s)...")
                
                for campaign_id, name, _, _, _ in paused_campaigns:
                    cursor.execute("""
                        UPDATE campaigns_campaign
                        SET status = 'running', updated_at = %s
                        WHERE id = %s;
                    """, (datetime.now(), campaign_id))
                    
                    # Log
                    cursor.execute("""
                        INSERT INTO campaigns_campaignlog (
                            id, campaign_id, log_type, severity, message,
                            details, created_at
                        )
                        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s);
                    """, (
                        campaign_id,
                        'resumed',
                        'info',
                        f'Campanha retomada via script de recovery',
                        '{"reason": "manual_recovery", "resumed_at": "' + datetime.now().isoformat() + '"}',
                        datetime.now()
                    ))
                    
                    print(f"   ✓ {name}")
                
                conn.commit()
                print("\n✅ Campanhas retomadas com sucesso!")
                print("\n📋 IMPORTANTE: Certifique-se que Celery Worker está rodando!")
        
        elif action == '3':
            campaign_id = input("\nDigite o ID da campanha: ").strip()
            
            cursor.execute("""
                SELECT id, name, status FROM campaigns_campaign
                WHERE id = %s;
            """, (campaign_id,))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                print(f"\n❌ Campanha não encontrada: {campaign_id}")
            else:
                _, name, status = campaign
                
                if status == 'running':
                    print(f"\n⚠️  Campanha '{name}' já está rodando!")
                else:
                    cursor.execute("""
                        UPDATE campaigns_campaign
                        SET status = 'running', updated_at = %s
                        WHERE id = %s;
                    """, (datetime.now(), campaign_id))
                    
                    conn.commit()
                    print(f"\n✅ Campanha '{name}' retomada com sucesso!")
        
        elif action == '4':
            campaign_id = input("\nDigite o ID da campanha: ").strip()
            
            cursor.execute("""
                SELECT 
                    log_type, severity, message, created_at
                FROM campaigns_campaignlog
                WHERE campaign_id = %s
                ORDER BY created_at DESC
                LIMIT 20;
            """, (campaign_id,))
            
            logs = cursor.fetchall()
            
            if not logs:
                print(f"\n⚠️  Nenhum log encontrado para esta campanha.")
            else:
                print(f"\n📋 Últimos {len(logs)} logs:\n")
                print("-" * 80)
                for log_type, severity, message, created_at in logs:
                    severity_icon = "🔴" if severity == 'error' else "⚠️" if severity == 'warning' else "ℹ️"
                    print(f"{severity_icon} [{created_at.strftime('%H:%M:%S')}] {log_type.upper()}")
                    print(f"   {message}")
                    print("-" * 80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    recover_campaigns()

