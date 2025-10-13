"""
🚨 PARADA EMERGENCIAL DE CAMPANHAS
Pausa TODAS as campanhas em execução imediatamente
"""
import psycopg2
from datetime import datetime

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def emergency_stop():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🚨 PARADA EMERGENCIAL DE CAMPANHAS")
        print("="*80)
        
        # Listar campanhas ativas
        cursor.execute("""
            SELECT id, name, status, messages_sent, total_contacts
            FROM campaigns_campaign
            WHERE status = 'running'
            ORDER BY created_at DESC;
        """)
        
        running_campaigns = cursor.fetchall()
        
        if not running_campaigns:
            print("\n✅ Nenhuma campanha em execução.")
            cursor.close()
            conn.close()
            return
        
        print(f"\n⚠️  {len(running_campaigns)} campanha(s) em execução:\n")
        print("-" * 80)
        
        for campaign in running_campaigns:
            campaign_id, name, status, messages_sent, total_contacts = campaign
            progress = (messages_sent / total_contacts * 100) if total_contacts > 0 else 0
            print(f"📊 {name}")
            print(f"   ID: {campaign_id}")
            print(f"   Status: {status}")
            print(f"   Progresso: {messages_sent}/{total_contacts} ({progress:.1f}%)")
            print("-" * 80)
        
        print(f"\n🚨 ATENÇÃO: Isso vai PAUSAR TODAS as {len(running_campaigns)} campanhas!")
        print("As mensagens que estiverem sendo enviadas serão interrompidas.")
        
        confirm = input("\n⚠️  Confirma PARADA EMERGENCIAL? Digite 'SIM' para confirmar: ")
        
        if confirm.upper() != 'SIM':
            print("\n❌ Operação cancelada.")
            cursor.close()
            conn.close()
            return
        
        print(f"\n🛑 Pausando {len(running_campaigns)} campanha(s)...")
        
        # Pausar todas as campanhas
        cursor.execute("""
            UPDATE campaigns_campaign
            SET status = 'paused',
                updated_at = %s
            WHERE status = 'running'
            RETURNING id, name;
        """, (datetime.now(),))
        
        paused_campaigns = cursor.fetchall()
        
        conn.commit()
        
        print("\n✅ CAMPANHAS PAUSADAS COM SUCESSO!\n")
        print("-" * 80)
        for campaign_id, name in paused_campaigns:
            print(f"✓ {name} (ID: {campaign_id})")
            
            # Criar log de parada emergencial
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
                f'Campanha pausada via PARADA EMERGENCIAL',
                '{"reason": "emergency_stop", "stopped_at": "' + datetime.now().isoformat() + '"}',
                datetime.now()
            ))
        
        conn.commit()
        print("-" * 80)
        
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Verificar o motivo da parada emergencial")
        print("2. Corrigir o problema")
        print("3. Usar o script 'recover_campaigns.py' para retomar as campanhas")
        print("4. Ou retomar manualmente pelo painel admin")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    emergency_stop()

