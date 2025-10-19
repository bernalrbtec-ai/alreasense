"""
🚀 Script para aplicar mudanças do Inbox no Railway
Roda diretamente via Railway CLI: railway run python apply_inbox_changes_railway.py
"""
import os
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import connection

def main():
    print("\n" + "="*70)
    print("📥 APLICANDO MUDANÇAS DO INBOX NO RAILWAY")
    print("="*70)
    
    with connection.cursor() as cursor:
        try:
            # 1. Verificar se tabela existe
            print("\n1️⃣  Verificando tabela chat_conversation...")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'chat_conversation'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("   ⚠️  Tabela chat_conversation não existe!")
                print("   Execute primeiro: python manage.py migrate chat")
                return False
            
            print("   ✅ Tabela existe")
            
            # 2. Verificar constraints atuais
            print("\n2️⃣  Verificando constraints de status...")
            cursor.execute("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_name LIKE '%conversation%status%'
                ORDER BY constraint_name;
            """)
            
            constraints = cursor.fetchall()
            if constraints:
                print(f"   📋 Constraints encontrados: {len(constraints)}")
                for name, clause in constraints:
                    print(f"      - {name}: {clause}")
            else:
                print("   ℹ️  Nenhum constraint de status encontrado")
            
            # 3. Dropar constraints antigos
            print("\n3️⃣  Removendo constraints antigos...")
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'chat_conversation' 
                AND constraint_type = 'CHECK' 
                AND constraint_name LIKE '%status%';
            """)
            
            dropped_count = 0
            for row in cursor.fetchall():
                constraint_name = row[0]
                try:
                    cursor.execute(f"""
                        ALTER TABLE chat_conversation 
                        DROP CONSTRAINT IF EXISTS {constraint_name};
                    """)
                    print(f"   🗑️  Removido: {constraint_name}")
                    dropped_count += 1
                except Exception as e:
                    print(f"   ⚠️  Erro ao remover {constraint_name}: {e}")
            
            if dropped_count == 0:
                print("   ℹ️  Nenhum constraint precisou ser removido")
            
            # 4. Criar novo constraint com 'pending'
            print("\n4️⃣  Adicionando status 'pending'...")
            try:
                cursor.execute("""
                    ALTER TABLE chat_conversation 
                    ADD CONSTRAINT chat_conversation_status_check 
                    CHECK (status IN ('pending', 'open', 'closed'));
                """)
                print("   ✅ Constraint criado com 'pending', 'open', 'closed'")
            except Exception as e:
                if 'already exists' in str(e).lower():
                    print("   ℹ️  Constraint já existe (OK)")
                else:
                    print(f"   ⚠️  Erro: {e}")
            
            # 5. Tornar department_id nullable
            print("\n5️⃣  Tornando department_id nullable (Inbox)...")
            cursor.execute("""
                SELECT is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'chat_conversation' 
                AND column_name = 'department_id';
            """)
            
            is_nullable = cursor.fetchone()[0]
            
            if is_nullable == 'NO':
                cursor.execute("""
                    ALTER TABLE chat_conversation 
                    ALTER COLUMN department_id DROP NOT NULL;
                """)
                print("   ✅ department_id agora aceita NULL")
            else:
                print("   ℹ️  department_id já aceita NULL (OK)")
            
            # 6. Verificar conversas existentes
            print("\n6️⃣  Verificando conversas existentes...")
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as total,
                    COUNT(CASE WHEN department_id IS NULL THEN 1 END) as sem_depto
                FROM chat_conversation
                GROUP BY status
                ORDER BY status;
            """)
            
            rows = cursor.fetchall()
            if rows:
                print("   📊 Status das conversas:")
                for status, total, sem_depto in rows:
                    depto_info = f" ({sem_depto} no Inbox)" if sem_depto > 0 else ""
                    print(f"      - {status}: {total} conversas{depto_info}")
            else:
                print("   ℹ️  Nenhuma conversa no banco ainda")
            
            print("\n" + "="*70)
            print("✅ INBOX CONFIGURADO COM SUCESSO!")
            print("="*70)
            print("\n📋 Resumo:")
            print("   ✅ Status 'pending' adicionado")
            print("   ✅ Conversas podem ficar sem departamento (Inbox)")
            print("   ✅ Sistema pronto para receber conversas não classificadas")
            print("\n🎯 Próximos passos:")
            print("   1. Teste enviando mensagem para o WhatsApp")
            print("   2. Conversa deve aparecer no tab 'Inbox'")
            print("   3. Qualquer agente/gerente pode 'pegar' a conversa")
            print("="*70 + "\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

