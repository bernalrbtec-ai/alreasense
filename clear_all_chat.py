"""
Script para zerar TUDO relacionado a chat e instâncias no Railway.
Respeita todas as foreign keys.
"""
import psycopg2

DB_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def main():
    print("\n" + "="*80)
    print("🗑️  ZERAR CHAT + INSTÂNCIAS - RAILWAY")
    print("="*80)
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        print("✅ Conectado ao banco Railway!")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Ver estatísticas antes
    print("\n📊 ESTATÍSTICAS ANTES:")
    
    tables_to_check = [
        'chat_attachment',
        'chat_message', 
        'chat_conversation',
        'campaigns_contact',
        'campaigns_message',
        'notifications_whatsapp_connection_log',
        'notifications_whatsapp_instance',
        'connections_evolutionconnection'
    ]
    
    stats = {}
    for table in tables_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table] = count
            print(f"  - {table}: {count}")
        except:
            stats[table] = 0
            print(f"  - {table}: 0 (não existe)")
    
    # Confirmar
    print("\n" + "="*80)
    print("⚠️  ATENÇÃO: Isso vai DELETAR TUDO relacionado a:")
    print("   - Chat (conversas, mensagens, anexos)")
    print("   - Campanhas (contatos, mensagens)")
    print("   - Instâncias WhatsApp")
    print("   - Conexões Evolution")
    print("\n   ISSO É IRREVERSÍVEL!")
    print("="*80)
    
    confirm = input("\n❓ Digite 'ZERAR TUDO' para confirmar: ")
    
    if confirm != 'ZERAR TUDO':
        print("\n❌ Operação cancelada")
        conn.close()
        return
    
    print("\n🗑️  Deletando...")
    
    try:
        # ORDEM CORRETA (do mais dependente para o menos)
        
        # 1. Chat: Anexos (depende de mensagens)
        cursor.execute("DELETE FROM chat_attachment")
        print(f"✅ Anexos: {cursor.rowcount} deletados")
        
        # 2. Chat: Mensagens (depende de conversas)
        cursor.execute("DELETE FROM chat_message")
        print(f"✅ Mensagens chat: {cursor.rowcount} deletadas")
        
        # 3. Chat: Participantes M2M
        cursor.execute("DELETE FROM chat_conversation_participants")
        print(f"✅ Participantes: {cursor.rowcount} deletados")
        
        # 4. Chat: Conversas
        cursor.execute("DELETE FROM chat_conversation")
        print(f"✅ Conversas: {cursor.rowcount} deletadas")
        
        # 5. Campanhas: Logs
        cursor.execute("DELETE FROM campaigns_log")
        print(f"✅ Logs campanhas: {cursor.rowcount} deletados")
        
        # 6. Campanhas: Contatos - REMOVER REFERÊNCIAS ANTES
        cursor.execute("UPDATE campaigns_contact SET instance_used_id = NULL WHERE instance_used_id IS NOT NULL")
        print(f"✅ Referências de instâncias removidas: {cursor.rowcount}")
        
        cursor.execute("UPDATE campaigns_contact SET message_used_id = NULL WHERE message_used_id IS NOT NULL")
        print(f"✅ Referências de mensagens removidas: {cursor.rowcount}")
        
        # 7. Campanhas: Mensagens (AGORA sim pode deletar)
        cursor.execute("DELETE FROM campaigns_message")
        print(f"✅ Mensagens campanhas: {cursor.rowcount} deletadas")
        
        # 8. Campanhas: Instâncias M2M (campaigns_campaign_instances)
        cursor.execute("DELETE FROM campaigns_campaign_instances")
        print(f"✅ Relação campanhas-instâncias: {cursor.rowcount} deletadas")
        
        # 9. Instâncias: Connection logs
        cursor.execute("DELETE FROM notifications_whatsapp_connection_log")
        print(f"✅ Connection logs: {cursor.rowcount} deletados")
        
        # 10. Instâncias: WhatsApp
        cursor.execute("DELETE FROM notifications_whatsapp_instance")
        print(f"✅ WhatsApp instances: {cursor.rowcount} deletadas")
        
        # 11. Conexões Evolution
        cursor.execute("DELETE FROM connections_evolutionconnection")
        print(f"✅ Evolution connections: {cursor.rowcount} deletadas")
        
        # Commit
        conn.commit()
        
        print("\n" + "="*80)
        print("✅ TUDO DELETADO COM SUCESSO!")
        print("="*80)
        
        # Mostrar estatísticas depois
        print("\n📊 ESTATÍSTICAS DEPOIS:")
        for table in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count}")
            except:
                print(f"  - {table}: 0 (não existe)")
        
        print("\n" + "="*80)
        print("🎉 BANCO LIMPO!")
        print("="*80)
        print("\n📋 PRÓXIMOS PASSOS:")
        print("   1. ✅ Código corrigido já está no Railway")
        print("   2. 🔧 Criar nova instância no Evolution API")
        print("   3. 📱 Criar registro no Flow Chat")
        print("   4. 🔗 Conectar (escanear QR code)")
        print("   5. ✅ Testar: nome/foto corretos + tempo real")
        print("\n💡 NÃO ESQUEÇA:")
        print("   - Adicionar variável: CHAT_LOG_LEVEL=WARNING")
        print("   - Isso reduz logs em 80-90%!")
        
    except Exception as e:
        print(f"\n❌ Erro ao deletar: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == '__main__':
    main()

