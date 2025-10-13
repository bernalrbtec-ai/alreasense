"""
📊 MONITOR DE CAMPANHAS EM TEMPO REAL
Monitora todas as campanhas ativas e mostra progresso
"""
import psycopg2
from datetime import datetime
import time
import os

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def clear_screen():
    """Limpa a tela do terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_campaign_stats(cursor):
    """Busca estatísticas das campanhas"""
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) FILTER (WHERE status = 'paused') as paused,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
            SUM(messages_sent) as total_sent,
            SUM(messages_delivered) as total_delivered,
            SUM(messages_failed) as total_failed
        FROM campaigns_campaign;
    """)
    
    return cursor.fetchone()

def get_active_campaigns(cursor):
    """Busca campanhas ativas"""
    cursor.execute("""
        SELECT 
            id, name, status, messages_sent, messages_delivered, 
            messages_failed, total_contacts, created_at, 
            last_message_sent_at
        FROM campaigns_campaign
        WHERE status IN ('running', 'paused')
        ORDER BY created_at DESC;
    """)
    
    return cursor.fetchall()

def format_progress_bar(current, total, width=30):
    """Cria uma barra de progresso visual"""
    if total == 0:
        return "[" + " " * width + "] 0%"
    
    progress = current / total
    filled = int(width * progress)
    bar = "█" * filled + "░" * (width - filled)
    percentage = progress * 100
    
    return f"[{bar}] {percentage:.1f}%"

def monitor_campaigns():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        
        print("🚀 Iniciando monitor de campanhas...")
        print("Pressione Ctrl+C para sair\n")
        time.sleep(2)
        
        while True:
            cursor = conn.cursor()
            
            # Buscar estatísticas
            stats = get_campaign_stats(cursor)
            running, paused, completed, cancelled, total_sent, total_delivered, total_failed = stats
            
            # Buscar campanhas ativas
            campaigns = get_active_campaigns(cursor)
            
            # Limpar tela
            clear_screen()
            
            # Header
            print("="*100)
            print("📊 MONITOR DE CAMPANHAS - ALREA SENSE")
            print(f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            print("="*100)
            
            # Estatísticas gerais
            print(f"\n📈 ESTATÍSTICAS GERAIS:")
            print(f"   ▶️  Em execução: {running or 0}")
            print(f"   ⏸️  Pausadas: {paused or 0}")
            print(f"   ✅ Completadas: {completed or 0}")
            print(f"   ❌ Canceladas: {cancelled or 0}")
            print(f"   📤 Total enviadas: {total_sent or 0}")
            print(f"   ✓  Total entregues: {total_delivered or 0}")
            print(f"   ✗  Total falhadas: {total_failed or 0}")
            
            # Campanhas ativas
            if campaigns:
                print(f"\n\n📋 CAMPANHAS ATIVAS ({len(campaigns)}):")
                print("-"*100)
                
                for campaign in campaigns:
                    campaign_id, name, status, sent, delivered, failed, total, created_at, last_message_at = campaign
                    
                    # Ícones de status
                    status_icon = "▶️" if status == 'running' else "⏸️"
                    
                    # Calcular progresso
                    progress_bar = format_progress_bar(sent or 0, total or 0, 40)
                    
                    # Calcular taxa de entrega
                    delivery_rate = (delivered / sent * 100) if sent and sent > 0 else 0
                    
                    # Tempo desde última mensagem
                    if last_message_at:
                        time_since = datetime.now(last_message_at.tzinfo) - last_message_at
                        minutes = int(time_since.total_seconds() / 60)
                        seconds = int(time_since.total_seconds() % 60)
                        last_msg_text = f"{minutes}m {seconds}s atrás"
                    else:
                        last_msg_text = "Nunca"
                    
                    # Exibir informações
                    print(f"\n{status_icon} {name}")
                    print(f"   ID: {campaign_id}")
                    print(f"   Progresso: {progress_bar} ({sent or 0}/{total or 0})")
                    print(f"   📤 Enviadas: {sent or 0} | ✓ Entregues: {delivered or 0} ({delivery_rate:.1f}%) | ✗ Falhadas: {failed or 0}")
                    print(f"   ⏰ Última mensagem: {last_msg_text}")
                    print(f"   🕐 Criada em: {created_at.strftime('%d/%m/%Y %H:%M:%S')}")
                    print("-"*100)
            else:
                print(f"\n\n✅ Nenhuma campanha ativa no momento.")
            
            # Footer
            print(f"\n💡 Dica: Use 'emergency_stop_campaigns.py' para parar todas as campanhas")
            print(f"💡 Dica: Use 'recover_campaigns.py' para recuperar campanhas travadas")
            print(f"\n🔄 Atualizando em 5 segundos... (Ctrl+C para sair)")
            
            cursor.close()
            
            # Aguardar 5 segundos antes de atualizar
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitor encerrado pelo usuário.")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    monitor_campaigns()

