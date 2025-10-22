"""
Script para zerar instâncias WhatsApp no Railway.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def main():
    print("\n" + "="*80)
    print("🗑️  ZERAR INSTÂNCIAS WHATSAPP - RAILWAY")
    print("="*80)
    
    # Conectar
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("✅ Conectado ao banco Railway!")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Ver o que tem
    print("\n📊 INSTÂNCIAS ATUAIS:")
    cursor.execute("""
        SELECT 
            w.id,
            w.friendly_name,
            w.instance_name,
            w.is_active,
            w.status,
            t.name as tenant_name
        FROM notifications_whatsapp_instance w
        LEFT JOIN tenancy_tenant t ON w.tenant_id = t.id
        ORDER BY w.created_at
    """)
    
    instances = cursor.fetchall()
    
    if not instances:
        print("\n✅ Nenhuma instância no banco!")
        conn.close()
        return
    
    print(f"\n📦 Total: {len(instances)} instâncias\n")
    
    for inst in instances:
        active_emoji = "✅" if inst['is_active'] else "❌"
        print(f"{active_emoji} {inst['friendly_name'] or '(sem nome)'}")
        print(f"  ID: {inst['id']}")
        print(f"  Instance name: {inst['instance_name']}")
        print(f"  Tenant: {inst['tenant_name'] or 'Global'}")
        print(f"  Status: {inst['status']}")
        print()
    
    # Confirmar
    print("="*80)
    print("⚠️  ATENÇÃO: Isso vai DELETAR TODAS as instâncias!")
    print("="*80)
    
    confirm = input("\n❓ Digite 'DELETAR TUDO' para confirmar: ")
    
    if confirm == 'DELETAR TUDO':
        try:
            # Deletar na ordem correta (respeitar foreign keys)
            # 1. Logs das instâncias
            cursor.execute("DELETE FROM notifications_whatsapp_connection_log")
            deleted_logs = cursor.rowcount
            
            # 2. WhatsApp instances
            cursor.execute("DELETE FROM notifications_whatsapp_instance")
            deleted_wa = cursor.rowcount
            
            # 3. Evolution connections
            cursor.execute("DELETE FROM connections_evolutionconnection")
            deleted_evo = cursor.rowcount
            conn.commit()
            
            print(f"\n✅ DELETADO:")
            print(f"  - {deleted_logs} Connection logs")
            print(f"  - {deleted_wa} WhatsApp instances")
            print(f"  - {deleted_evo} Evolution connections")
            print("\n📋 Banco zerado! Agora pode:")
            print("   1. Criar nova instância no Evolution")
            print("   2. Criar registro no Flow Chat")
            print("   3. Conectar e testar")
        except Exception as e:
            print(f"\n❌ Erro ao deletar: {e}")
            conn.rollback()
    else:
        print("\n❌ Operação cancelada")
    
    conn.close()

if __name__ == '__main__':
    main()

