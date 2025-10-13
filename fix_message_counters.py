"""
🔧 CORREÇÃO DE CONTADORES DE MENSAGENS
Recalcula contadores de mensagens baseado nas campanhas e webhooks
"""
import psycopg2
from datetime import datetime, timedelta
from django.utils import timezone

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def fix_message_counters():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("="*80)
        print("🔧 CORREÇÃO DE CONTADORES DE MENSAGENS")
        print("="*80)
        
        # 1. Verificar mensagens no banco
        print("\n📊 VERIFICANDO MENSAGENS NO BANCO:")
        print("-" * 80)
        
        # Contar mensagens por tenant
        cursor.execute("""
            SELECT 
                t.id,
                t.name,
                COUNT(m.id) as total_messages,
                COUNT(CASE WHEN m.created_at >= CURRENT_DATE THEN m.id END) as messages_today,
                COUNT(CASE WHEN m.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN m.id END) as messages_30_days
            FROM tenancy_tenant t
            LEFT JOIN messages_message m ON m.tenant_id = t.id
            GROUP BY t.id, t.name
            ORDER BY t.name;
        """)
        
        tenant_stats = cursor.fetchall()
        
        for tenant_id, tenant_name, total, today, last_30 in tenant_stats:
            print(f"🏢 {tenant_name}")
            print(f"   Total: {total}")
            print(f"   Hoje: {today}")
            print(f"   Últimos 30 dias: {last_30}")
            print("-" * 80)
        
        # 2. Verificar campanhas e mensagens enviadas
        print("\n📈 VERIFICANDO CAMPANHAS:")
        print("-" * 80)
        
        cursor.execute("""
            SELECT 
                t.name as tenant_name,
                c.name as campaign_name,
                c.status,
                c.total_contacts,
                c.messages_sent,
                c.messages_delivered,
                c.messages_failed,
                c.created_at
            FROM campaigns_campaign c
            JOIN tenancy_tenant t ON t.id = c.tenant_id
            ORDER BY t.name, c.created_at DESC;
        """)
        
        campaigns = cursor.fetchall()
        
        total_campaign_messages = 0
        for tenant_name, campaign_name, status, total_contacts, sent, delivered, failed, created_at in campaigns:
            print(f"📊 {campaign_name} ({tenant_name})")
            print(f"   Status: {status}")
            print(f"   Contatos: {total_contacts}")
            print(f"   Enviadas: {sent}")
            print(f"   Entregues: {delivered}")
            print(f"   Falhadas: {failed}")
            print(f"   Criada: {created_at.strftime('%d/%m/%Y %H:%M')}")
            print("-" * 80)
            total_campaign_messages += sent or 0
        
        print(f"\n📊 TOTAL DE MENSAGENS ENVIADAS EM CAMPANHAS: {total_campaign_messages}")
        
        # 3. Verificar se há mensagens no modelo Message
        cursor.execute("SELECT COUNT(*) FROM messages_message;")
        total_messages_in_db = cursor.fetchone()[0]
        
        print(f"📊 TOTAL DE MENSAGENS NO MODELO MESSAGE: {total_messages_in_db}")
        
        # 4. Análise do problema
        print("\n🔍 ANÁLISE DO PROBLEMA:")
        print("-" * 80)
        
        if total_campaign_messages > 0 and total_messages_in_db == 0:
            print("❌ PROBLEMA IDENTIFICADO:")
            print("   - Campanhas enviaram mensagens, mas nenhuma foi salva no modelo Message")
            print("   - O webhook não está funcionando ou não está sendo chamado")
            print("   - As mensagens das campanhas não estão sendo registradas para contagem")
        elif total_campaign_messages > total_messages_in_db:
            print("⚠️  PROBLEMA PARCIAL:")
            print(f"   - Campanhas enviaram {total_campaign_messages} mensagens")
            print(f"   - Apenas {total_messages_in_db} foram salvas no modelo Message")
            print("   - Algumas mensagens não estão sendo registradas")
        else:
            print("✅ CONTADORES PARECEM CORRETOS")
        
        # 5. Soluções propostas
        print("\n💡 SOLUÇÕES PROPOSTAS:")
        print("-" * 80)
        print("1. Corrigir webhook para salvar mensagens das campanhas")
        print("2. Criar mensagens 'sintéticas' baseadas nas campanhas")
        print("3. Modificar API de métricas para usar dados das campanhas")
        print("4. Verificar se Evolution API está enviando webhooks")
        
        # 6. Opção de correção rápida
        if total_campaign_messages > 0 and total_messages_in_db == 0:
            print("\n🔧 CORREÇÃO RÁPIDA DISPONÍVEL:")
            print("-" * 80)
            print("Posso criar mensagens sintéticas baseadas nas campanhas para corrigir os contadores.")
            
            confirm = input("\n⚠️  Deseja criar mensagens sintéticas? (SIM/não): ")
            
            if confirm.upper() == 'SIM':
                print("\n🔄 Criando mensagens sintéticas...")
                
                # Buscar campanhas com mensagens enviadas
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.tenant_id,
                        c.name,
                        c.messages_sent,
                        c.created_at
                    FROM campaigns_campaign c
                    WHERE c.messages_sent > 0
                    ORDER BY c.created_at;
                """)
                
                campaigns_with_messages = cursor.fetchall()
                
                messages_created = 0
                for campaign_id, tenant_id, campaign_name, messages_sent, created_at in campaigns_with_messages:
                    print(f"   📊 Processando campanha: {campaign_name} ({messages_sent} mensagens)")
                    
                    # Criar mensagens sintéticas
                    for i in range(messages_sent):
                        # Criar uma mensagem sintética para cada mensagem enviada
                        cursor.execute("""
                            INSERT INTO messages_message (
                                tenant_id, chat_id, sender, text, created_at
                            )
                            VALUES (
                                %s,
                                %s,
                                %s,
                                %s,
                                %s
                            );
                        """, (
                            tenant_id,
                            f"campaign_{campaign_id}",
                            'bot',
                            f'Mensagem da campanha: {campaign_name}',
                            created_at + timedelta(minutes=i)  # Distribuir ao longo do tempo
                        ))
                        messages_created += 1
                
                conn.commit()
                print(f"\n✅ {messages_created} mensagens sintéticas criadas!")
                
                # Verificar resultado
                cursor.execute("SELECT COUNT(*) FROM messages_message;")
                new_total = cursor.fetchone()[0]
                print(f"📊 Total de mensagens agora: {new_total}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    fix_message_counters()

