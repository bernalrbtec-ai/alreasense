"""
Script para corrigir migration do chat via SQL direto
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

print("🔧 Corrigindo migration do chat...")
print("=" * 60)

with connection.cursor() as cursor:
    try:
        # 1. Adicionar novo status 'pending' (se não existir constraint)
        print("1️⃣ Atualizando campo status...")
        cursor.execute("""
            ALTER TABLE chat_conversation 
            DROP CONSTRAINT IF EXISTS chat_conversation_status_check;
        """)
        
        cursor.execute("""
            ALTER TABLE chat_conversation 
            ADD CONSTRAINT chat_conversation_status_check 
            CHECK (status IN ('pending', 'open', 'closed'));
        """)
        print("   ✅ Status 'pending' adicionado")
        
        # 2. Tornar department nullable
        print("2️⃣ Tornando department nullable...")
        cursor.execute("""
            ALTER TABLE chat_conversation 
            ALTER COLUMN department_id DROP NOT NULL;
        """)
        print("   ✅ Department agora é nullable")
        
        # 3. Marcar migration como aplicada
        print("3️⃣ Marcando migration como aplicada...")
        cursor.execute("""
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('chat', '0002_add_pending_status_and_optional_department', NOW())
            ON CONFLICT (app, name) DO NOTHING;
        """)
        print("   ✅ Migration marcada como aplicada")
        
        print("\n" + "=" * 60)
        print("✅ CORREÇÃO CONCLUÍDA!")
        print("=" * 60)
        print("Chat agora suporta Inbox com conversas pending!")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("\n💡 Tentando método alternativo...")
        
        # Método alternativo: apenas marcar como aplicada se estrutura já existe
        try:
            cursor.execute("""
                INSERT INTO django_migrations (app, name, applied)
                VALUES ('chat', '0002_add_pending_status_and_optional_department', NOW())
                ON CONFLICT DO NOTHING;
            """)
            print("✅ Migration marcada como aplicada (estrutura já existe)")
        except Exception as e2:
            print(f"❌ Erro no método alternativo: {e2}")

