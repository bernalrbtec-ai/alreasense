#!/usr/bin/env python
"""
Script completo para verificar e corrigir toda a estrutura do banco de dados.
Verifica tabelas, colunas, tipos de dados, índices, etc.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def verify_and_fix_database():
    """Verify and fix the entire database structure."""
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO COMPLETA DO BANCO DE DADOS")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        # 1. Verificar extensões PostgreSQL
        print("\n1️⃣ VERIFICANDO EXTENSÕES POSTGRESQL...")
        cursor.execute("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname IN ('vector', 'uuid-ossp', 'pgcrypto');
        """)
        extensions = cursor.fetchall()
        
        if extensions:
            for ext_name, ext_version in extensions:
                print(f"   ✅ {ext_name}: versão {ext_version}")
        else:
            print("   ℹ️  Nenhuma extensão especial instalada")
        
        # Verificar se vector está disponível
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_available_extensions WHERE name = 'vector'
            );
        """)
        vector_available = cursor.fetchone()[0]
        if vector_available:
            print("   ℹ️  Extensão 'vector' disponível mas não instalada (OK por enquanto)")
        
        # 2. Verificar tabelas principais
        print("\n2️⃣ VERIFICANDO TABELAS PRINCIPAIS...")
        expected_tables = [
            'tenancy_tenant',
            'authn_user',
            'connections_evolutionconnection',
            'chat_messages_message',
            'notifications_whatsapp_instance',
            'notifications_whatsapp_connection_log',
            'notifications_smtp_config',
            'notifications_notification_log',
            'billing_plan',
            'billing_paymentaccount',
            'experiments_prompttemplate',
            'experiments_inference',
        ]
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table in expected_tables:
            if table in existing_tables:
                # Contar registros
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cursor.fetchone()[0]
                    print(f"   ✅ {table:<45} ({count} registros)")
                except Exception as e:
                    print(f"   ⚠️  {table:<45} (erro ao contar: {e})")
            else:
                print(f"   ❌ {table:<45} (NÃO EXISTE)")
        
        # 3. Verificar estrutura de connections_evolutionconnection
        print("\n3️⃣ VERIFICANDO ESTRUTURA: connections_evolutionconnection")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'connections_evolutionconnection'
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        """)
        
        expected_columns = {
            'id': 'integer',
            'tenant_id': 'uuid',
            'name': 'character varying',
            'base_url': 'character varying',
            'api_key': 'character varying',  # DEVE SER VARCHAR, NÃO BYTEA
            'webhook_url': 'character varying',
            'is_active': 'boolean',
            'status': 'character varying',
            'last_check': 'timestamp with time zone',
            'last_error': 'text',
            'created_at': 'timestamp with time zone',
            'updated_at': 'timestamp with time zone',
        }
        
        columns = cursor.fetchall()
        for col_name, data_type, is_nullable, col_default in columns:
            expected_type = expected_columns.get(col_name)
            type_match = expected_type in data_type if expected_type else False
            
            if expected_type and type_match:
                print(f"   ✅ {col_name:<20} {data_type:<25} NULL={is_nullable}")
            elif expected_type:
                print(f"   ⚠️  {col_name:<20} {data_type:<25} (esperado: {expected_type})")
            else:
                print(f"   ℹ️  {col_name:<20} {data_type:<25} (extra/legacy)")
        
        # Verificar se api_key está como bytea (problema!)
        cursor.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'connections_evolutionconnection'
            AND column_name = 'api_key';
        """)
        result = cursor.fetchone()
        if result and result[0] == 'bytea':
            print(f"\n   🔴 PROBLEMA: api_key está como BYTEA (criptografado)!")
            print(f"   ✅ Migration 0005 vai corrigir isso para VARCHAR")
        elif result:
            print(f"\n   ✅ api_key está correto: {result[0]}")
        
        # 4. Verificar estrutura de notifications_whatsapp_instance
        print("\n4️⃣ VERIFICANDO ESTRUTURA: notifications_whatsapp_instance")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'notifications_whatsapp_instance'
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        """)
        
        whatsapp_expected = {
            'id': 'uuid',
            'tenant_id': 'uuid',
            'friendly_name': 'character varying',
            'instance_name': 'character varying',
            'api_url': 'character varying',
            'api_key': 'character varying',  # DEVE SER VARCHAR, NÃO BYTEA
            'phone_number': 'character varying',
            'qr_code': 'text',
            'qr_code_expires_at': 'timestamp',
            'connection_state': 'character varying',
            'status': 'character varying',
            'last_check': 'timestamp',
            'last_error': 'text',
            'is_active': 'boolean',
            'is_default': 'boolean',
        }
        
        whatsapp_columns = cursor.fetchall()
        for col_name, data_type, is_nullable in whatsapp_columns:
            expected_type = whatsapp_expected.get(col_name)
            type_match = expected_type in data_type if expected_type else False
            
            if expected_type and type_match:
                print(f"   ✅ {col_name:<25} {data_type:<30}")
            elif expected_type:
                print(f"   ⚠️  {col_name:<25} {data_type:<30} (esperado: {expected_type})")
            else:
                print(f"   ℹ️  {col_name:<25} {data_type:<30} (extra)")
        
        # Verificar api_key
        cursor.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'notifications_whatsapp_instance'
            AND column_name = 'api_key';
        """)
        result = cursor.fetchone()
        if result and result[0] == 'bytea':
            print(f"\n   🔴 PROBLEMA: api_key está como BYTEA (criptografado)!")
            print(f"   ✅ Migration 0010 vai corrigir isso para VARCHAR")
        elif result:
            print(f"\n   ✅ api_key está correto: {result[0]}")
        
        # 5. Verificar índices importantes
        print("\n5️⃣ VERIFICANDO ÍNDICES...")
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename IN (
                'chat_messages_message',
                'connections_evolutionconnection',
                'notifications_whatsapp_instance'
            )
            ORDER BY tablename, indexname;
        """)
        
        indexes = cursor.fetchall()
        if indexes:
            current_table = None
            for schema, table, index_name, index_def in indexes:
                if table != current_table:
                    print(f"\n   📋 {table}:")
                    current_table = table
                print(f"      - {index_name}")
        else:
            print("   ℹ️  Nenhum índice customizado encontrado")
        
        # 6. Verificar constraints
        print("\n6️⃣ VERIFICANDO CONSTRAINTS...")
        cursor.execute("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
            AND tc.table_name IN (
                'connections_evolutionconnection',
                'notifications_whatsapp_instance'
            )
            AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
            ORDER BY tc.table_name, tc.constraint_type;
        """)
        
        constraints = cursor.fetchall()
        if constraints:
            current_table = None
            for table_name, constraint_name, constraint_type in constraints:
                if table_name != current_table:
                    print(f"\n   📋 {table_name}:")
                    current_table = table_name
                print(f"      {constraint_type}: {constraint_name}")
        
        # 7. Verificar dados problemáticos
        print("\n7️⃣ VERIFICANDO DADOS PROBLEMÁTICOS...")
        
        # Connections com api_key NULL
        cursor.execute("""
            SELECT COUNT(*) 
            FROM connections_evolutionconnection 
            WHERE api_key IS NULL;
        """)
        null_api_keys = cursor.fetchone()[0]
        if null_api_keys > 0:
            print(f"   ⚠️  {null_api_keys} conexões Evolution sem API key")
        else:
            print(f"   ✅ Todas as conexões Evolution têm API key")
        
        # WhatsApp instances sem tenant
        try:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM notifications_whatsapp_instance 
                WHERE tenant_id IS NULL;
            """)
            null_tenants = cursor.fetchone()[0]
            if null_tenants > 0:
                print(f"   ℹ️  {null_tenants} instâncias WhatsApp sem tenant (globais - OK)")
            else:
                print(f"   ✅ Todas as instâncias WhatsApp têm tenant")
        except:
            pass
        
        # 8. Resumo final
        print("\n" + "=" * 80)
        print("📊 RESUMO DA VERIFICAÇÃO")
        print("=" * 80)
        
        # Total de tabelas
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE';
        """)
        total_tables = cursor.fetchone()[0]
        print(f"\n   📋 Total de tabelas: {total_tables}")
        
        # Total de registros em tabelas principais
        main_tables = {
            'tenancy_tenant': 'Tenants',
            'authn_user': 'Usuários',
            'connections_evolutionconnection': 'Servidores Evolution',
            'notifications_whatsapp_instance': 'Instâncias WhatsApp',
            'chat_messages_message': 'Mensagens',
            'billing_plan': 'Planos',
        }
        
        print(f"\n   📊 Registros por tabela:")
        for table, friendly_name in main_tables.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"      {friendly_name:<25}: {count}")
            except:
                print(f"      {friendly_name:<25}: Tabela não existe")
    
    print("\n" + "=" * 80)
    print("✅ VERIFICAÇÃO CONCLUÍDA!")
    print("=" * 80)

if __name__ == '__main__':
    try:
        verify_and_fix_database()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

