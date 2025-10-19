"""
Script para aplicar mudanças do Inbox via SQL direto (sem Django migrations)
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

print("🔧 Aplicando mudanças do Inbox no banco...")
print("=" * 60)

with connection.cursor() as cursor:
    try:
        # 1. Verificar se tabela existe
        print("1️⃣ Verificando tabela chat_conversation...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'chat_conversation'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("   ⚠️  Tabela não existe - será criada pela migration 0001")
            sys.exit(0)
        
        print("   ✅ Tabela existe")
        
        # 2. Verificar e atualizar constraint de status
        print("2️⃣ Atualizando campo status...")
        
        # Dropar constraint antiga se existir
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'chat_conversation' 
            AND constraint_type = 'CHECK' 
            AND constraint_name LIKE '%status%';
        """)
        
        for row in cursor.fetchall():
            constraint_name = row[0]
            cursor.execute(f"ALTER TABLE chat_conversation DROP CONSTRAINT IF EXISTS {constraint_name};")
            print(f"   🗑️  Removido constraint: {constraint_name}")
        
        # Criar novo constraint com 'pending'
        cursor.execute("""
            ALTER TABLE chat_conversation 
            ADD CONSTRAINT chat_conversation_status_check 
            CHECK (status IN ('pending', 'open', 'closed'));
        """)
        print("   ✅ Status 'pending' adicionado ao CHECK constraint")
        
        # 3. Tornar department_id nullable
        print("3️⃣ Tornando department_id nullable...")
        cursor.execute("""
            ALTER TABLE chat_conversation 
            ALTER COLUMN department_id DROP NOT NULL;
        """)
        print("   ✅ department_id agora aceita NULL (conversas no Inbox)")
        
        print("\n" + "=" * 60)
        print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("📥 Chat agora suporta Inbox para conversas pendentes!")
        print("🔸 Status 'pending' disponível")
        print("🔸 Conversas podem ficar sem departamento (Inbox)")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

