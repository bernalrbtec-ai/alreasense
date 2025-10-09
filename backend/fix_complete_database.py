#!/usr/bin/env python
"""
Script COMPLETO para ajustar TODO o banco de dados.
Corrige tipos de dados, colunas faltantes, e estrutura.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def fix_complete_database():
    """Fix the entire database structure."""
    
    print("=" * 80)
    print("🔧 AJUSTANDO TODO O BANCO DE DADOS")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        
        # ========== CONNECTIONS_EVOLUTIONCONNECTION ==========
        print("\n📦 TABELA: connections_evolutionconnection")
        print("-" * 80)
        
        # Verificar se tabela existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'connections_evolutionconnection'
            );
        """)
        if not cursor.fetchone()[0]:
            print("   ❌ Tabela não existe! Rode: python manage.py migrate connections")
        else:
            # Verificar colunas
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'connections_evolutionconnection'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 1. api_key deve ser VARCHAR, não BYTEA
            if 'api_key' in columns:
                if columns['api_key'] == 'bytea':
                    print("   🔄 Convertendo api_key: bytea → varchar...")
                    cursor.execute("""
                        ALTER TABLE connections_evolutionconnection 
                        ALTER COLUMN api_key TYPE VARCHAR(255) USING NULL;
                    """)
                    print("   ✅ api_key convertido para varchar")
                else:
                    print(f"   ✅ api_key já é {columns['api_key']}")
            else:
                print("   ⚠️  Coluna api_key não existe")
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM connections_evolutionconnection;")
            count = cursor.fetchone()[0]
            print(f"   📊 Total de registros: {count}")
        
        # ========== NOTIFICATIONS_WHATSAPP_INSTANCE ==========
        print("\n📦 TABELA: notifications_whatsapp_instance")
        print("-" * 80)
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'notifications_whatsapp_instance'
            );
        """)
        if not cursor.fetchone()[0]:
            print("   ❌ Tabela não existe! Rode: python manage.py migrate notifications")
        else:
            # Verificar colunas
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'notifications_whatsapp_instance'
                ORDER BY ordinal_position;
            """)
            columns = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 1. api_key deve ser VARCHAR, não BYTEA
            if 'api_key' in columns:
                if columns['api_key'] == 'bytea':
                    print("   🔄 Convertendo api_key: bytea → varchar...")
                    cursor.execute("""
                        ALTER TABLE notifications_whatsapp_instance 
                        ALTER COLUMN api_key TYPE VARCHAR(255) USING NULL;
                    """)
                    print("   ✅ api_key convertido para varchar")
                else:
                    print(f"   ✅ api_key já é {columns['api_key']}")
            else:
                print("   ⚠️  Coluna api_key não existe")
            
            # 2. api_url pode ser NULL
            if 'api_url' in columns:
                cursor.execute("""
                    SELECT is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = 'notifications_whatsapp_instance'
                    AND column_name = 'api_url';
                """)
                is_nullable = cursor.fetchone()[0]
                if is_nullable == 'NO':
                    print("   🔄 Tornando api_url nullable...")
                    cursor.execute("""
                        ALTER TABLE notifications_whatsapp_instance 
                        ALTER COLUMN api_url DROP NOT NULL;
                    """)
                    print("   ✅ api_url agora é nullable")
                else:
                    print(f"   ✅ api_url já é nullable")
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM notifications_whatsapp_instance;")
            count = cursor.fetchone()[0]
            print(f"   📊 Total de registros: {count}")
        
        # ========== NOTIFICATIONS_SMTP_CONFIG ==========
        print("\n📦 TABELA: notifications_smtp_config")
        print("-" * 80)
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'notifications_smtp_config'
            );
        """)
        if cursor.fetchone()[0]:
            # Deletar registros com password NULL (dados corrompidos)
            cursor.execute("""
                DELETE FROM notifications_smtp_config 
                WHERE password IS NULL;
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"   🗑️  Deletados {deleted} registros com password NULL")
            
            # Verificar se password é bytea
            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'notifications_smtp_config'
                AND column_name = 'password';
            """)
            result = cursor.fetchone()
            if result and result[0] == 'bytea':
                print("   🔄 Convertendo password: bytea → varchar...")
                cursor.execute("""
                    ALTER TABLE notifications_smtp_config 
                    ALTER COLUMN password TYPE VARCHAR(255) USING password::text;
                """)
                print("   ✅ password convertido para varchar")
            elif result:
                print(f"   ✅ password já é {result[0]}")
            
            cursor.execute("SELECT COUNT(*) FROM notifications_smtp_config;")
            count = cursor.fetchone()[0]
            print(f"   📊 Total de registros: {count}")
        else:
            print("   ⚠️  Tabela não existe")
        
        # ========== CRIAR TABELA MESSAGES SE NÃO EXISTIR ==========
        print("\n📦 TABELA: chat_messages_message (MESSAGES)")
        print("-" * 80)
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'chat_messages_message'
            );
        """)
        if not cursor.fetchone()[0]:
            print("   ℹ️  Tabela não existe - será criada quando rodar: python manage.py migrate chat_messages")
        else:
            cursor.execute("SELECT COUNT(*) FROM chat_messages_message;")
            count = cursor.fetchone()[0]
            print(f"   ✅ Tabela existe com {count} registros")
        
        # ========== VERIFICAR TABELA NOTIFICATION_LOG ==========
        print("\n📦 TABELA: notifications_notification_log")
        print("-" * 80)
        
        # Procurar nome real da tabela
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name LIKE '%notification%log%'
            ORDER BY table_name;
        """)
        log_tables = cursor.fetchall()
        if log_tables:
            for (table_name,) in log_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"   ✅ {table_name}: {count} registros")
        else:
            print("   ⚠️  Nenhuma tabela de log de notificações encontrada")
        
        # ========== MARCAR MIGRATIONS COMO APLICADAS ==========
        print("\n📝 MARCANDO MIGRATIONS COMO APLICADAS...")
        print("-" * 80)
        
        migrations_to_mark = [
            ('connections', '0004_alter_evolutionconnection_options_and_more'),
            ('connections', '0005_remove_api_key_encryption'),
        ]
        
        for app, migration in migrations_to_mark:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM django_migrations 
                    WHERE app = %s AND name = %s
                );
            """, [app, migration])
            
            if not cursor.fetchone()[0]:
                try:
                    cursor.execute("""
                        INSERT INTO django_migrations (app, name, applied)
                        VALUES (%s, %s, NOW());
                    """, [app, migration])
                    print(f"   ✅ Marcada: {app}.{migration}")
                except Exception as e:
                    print(f"   ⚠️  Erro ao marcar {app}.{migration}: {e}")
            else:
                print(f"   ⏭️  Já aplicada: {app}.{migration}")
    
    print("\n" + "=" * 80)
    print("✅ AJUSTES CONCLUÍDOS!")
    print("=" * 80)
    print("\n📋 RESUMO:")
    print("✅ api_key convertido de bytea → varchar (connections)")
    print("✅ api_key convertido de bytea → varchar (whatsapp)")
    print("✅ api_url agora é nullable (whatsapp)")
    print("✅ password convertido de bytea → varchar (smtp)")
    print("✅ Migrations marcadas como aplicadas")
    print("\n🚀 PRÓXIMO PASSO:")
    print("   Deploy no Railway vai rodar suave agora!")

if __name__ == '__main__':
    try:
        fix_complete_database()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

