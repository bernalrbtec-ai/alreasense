"""
🗑️ Script para limpar todo o histórico do chat
Remove todas as conversas e mensagens do Flow Chat
"""
import os
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.chat.models import Conversation, Message, MessageAttachment
from django.db import connection

def main():
    print("\n" + "="*70)
    print("🗑️  LIMPEZA COMPLETA DO HISTÓRICO DO CHAT")
    print("="*70)
    
    # Contar antes
    print("\n📊 Estado atual:")
    conv_count = Conversation.objects.count()
    msg_count = Message.objects.count()
    attach_count = MessageAttachment.objects.count()
    
    print(f"   📁 Conversas: {conv_count}")
    print(f"   💬 Mensagens: {msg_count}")
    print(f"   📎 Anexos: {attach_count}")
    
    if conv_count == 0 and msg_count == 0:
        print("\n✅ Chat já está vazio!")
        return
    
    # Confirmar
    print("\n⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!")
    print("   Todas as conversas e mensagens serão PERMANENTEMENTE apagadas.")
    
    # Para Railway, sempre confirmar automaticamente
    if os.getenv('RAILWAY_ENVIRONMENT'):
        confirm = 'sim'
        print("   🚂 Ambiente Railway detectado - prosseguindo automaticamente...")
    else:
        confirm = input("\n❓ Digite 'sim' para confirmar: ").lower().strip()
    
    if confirm != 'sim':
        print("\n❌ Operação cancelada pelo usuário.")
        return
    
    print("\n🗑️  Iniciando limpeza...")
    
    try:
        # 1. Deletar anexos primeiro (FK para mensagens)
        if attach_count > 0:
            print(f"\n1️⃣  Deletando {attach_count} anexos...")
            MessageAttachment.objects.all().delete()
            print("   ✅ Anexos deletados")
        
        # 2. Deletar mensagens
        if msg_count > 0:
            print(f"\n2️⃣  Deletando {msg_count} mensagens...")
            Message.objects.all().delete()
            print("   ✅ Mensagens deletadas")
        
        # 3. Deletar conversas
        if conv_count > 0:
            print(f"\n3️⃣  Deletando {conv_count} conversas...")
            Conversation.objects.all().delete()
            print("   ✅ Conversas deletadas")
        
        # 4. Resetar sequences (IDs)
        print("\n4️⃣  Resetando sequences...")
        with connection.cursor() as cursor:
            # Verificar se as tabelas usam sequences (não UUID)
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'chat_conversation' 
                AND column_name = 'id';
            """)
            result = cursor.fetchone()
            
            if result and result[1] != 'uuid':
                # Resetar sequences apenas se não for UUID
                cursor.execute("""
                    DO $$ 
                    DECLARE 
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'chat_%') LOOP
                            EXECUTE 'ALTER SEQUENCE IF EXISTS ' || quote_ident(r.tablename || '_id_seq') || ' RESTART WITH 1';
                        END LOOP;
                    END $$;
                """)
                print("   ✅ Sequences resetadas")
            else:
                print("   ℹ️  IDs são UUID (não precisa resetar)")
        
        print("\n" + "="*70)
        print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("="*70)
        print("\n🎉 Chat zerado! Pode começar do zero agora.")
        print("\n📝 Verificando estado final...")
        
        # Verificar final
        print(f"   📁 Conversas: {Conversation.objects.count()}")
        print(f"   💬 Mensagens: {Message.objects.count()}")
        print(f"   📎 Anexos: {MessageAttachment.objects.count()}")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO durante limpeza: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

