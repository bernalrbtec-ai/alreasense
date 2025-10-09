#!/usr/bin/env python
"""
Script para corrigir a tabela connections_evolutionconnection.
Remove colunas antigas e garante que a estrutura está correta.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def fix_evolution_connection_table():
    """Fix the Evolution Connection table structure."""
    
    print("=" * 60)
    print("🔧 CORRIGINDO TABELA connections_evolutionconnection")
    print("=" * 60)
    
    with connection.cursor() as cursor:
        # 1. Verificar quais colunas existem
        print("\n1️⃣ Verificando colunas existentes...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'connections_evolutionconnection'
            AND table_schema = 'public';
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}
        print(f"   Colunas encontradas: {', '.join(sorted(existing_columns))}")
        
        # 2. Remover colunas antigas se existirem
        print("\n2️⃣ Removendo colunas antigas...")
        old_columns = ['evo_token', 'evo_ws_url']
        for col in old_columns:
            if col in existing_columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE connections_evolutionconnection 
                        DROP COLUMN IF EXISTS {col} CASCADE;
                    """)
                    print(f"   ✅ Removida coluna: {col}")
                except Exception as e:
                    print(f"   ⚠️  Erro ao remover {col}: {e}")
            else:
                print(f"   ⏭️  Coluna {col} não existe (OK)")
        
        # 3. Adicionar colunas novas se não existirem
        print("\n3️⃣ Adicionando colunas novas...")
        
        new_columns = {
            'api_key': 'bytea NULL',
            'base_url': 'VARCHAR(200) NULL',
            'last_check': 'TIMESTAMP WITH TIME ZONE NULL',
            'last_error': 'TEXT NULL',
            'status': "VARCHAR(20) DEFAULT 'inactive' NOT NULL",
            'webhook_url': 'VARCHAR(200) NULL',
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"""
                        ALTER TABLE connections_evolutionconnection 
                        ADD COLUMN {col_name} {col_type};
                    """)
                    print(f"   ✅ Adicionada coluna: {col_name} ({col_type})")
                except Exception as e:
                    print(f"   ⚠️  Erro ao adicionar {col_name}: {e}")
            else:
                print(f"   ⏭️  Coluna {col_name} já existe (OK)")
        
        # 4. Verificar estrutura final
        print("\n4️⃣ Verificando estrutura final...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'connections_evolutionconnection'
            AND table_schema = 'public'
            ORDER BY column_name;
        """)
        
        print("\n   Estrutura final da tabela:")
        print("   " + "-" * 70)
        print(f"   {'COLUNA':<20} {'TIPO':<20} {'NULL':<10} {'DEFAULT':<20}")
        print("   " + "-" * 70)
        
        for row in cursor.fetchall():
            col_name, data_type, is_nullable, col_default = row
            col_default = col_default or ''
            if len(col_default) > 20:
                col_default = col_default[:17] + '...'
            print(f"   {col_name:<20} {data_type:<20} {is_nullable:<10} {col_default:<20}")
        print("   " + "-" * 70)
        
        # 5. Contar registros
        print("\n5️⃣ Verificando registros existentes...")
        cursor.execute("""
            SELECT COUNT(*) FROM connections_evolutionconnection;
        """)
        count = cursor.fetchone()[0]
        print(f"   Total de registros: {count}")
        
        if count > 0:
            cursor.execute("""
                SELECT id, name, base_url, status, is_active
                FROM connections_evolutionconnection
                ORDER BY created_at DESC
                LIMIT 5;
            """)
            print("\n   Últimos 5 registros:")
            print("   " + "-" * 70)
            print(f"   {'ID':<10} {'NOME':<20} {'URL':<25} {'STATUS':<10} {'ATIVO':<10}")
            print("   " + "-" * 70)
            for row in cursor.fetchall():
                id_val, name, base_url, status, is_active = row
                base_url = base_url or 'NULL'
                if len(base_url) > 25:
                    base_url = base_url[:22] + '...'
                print(f"   {id_val:<10} {name:<20} {base_url:<25} {status:<10} {str(is_active):<10}")
            print("   " + "-" * 70)
    
    print("\n" + "=" * 60)
    print("✅ CORREÇÃO CONCLUÍDA!")
    print("=" * 60)
    print("\nPRÓXIMOS PASSOS:")
    print("1. Marcar migration 0004 como aplicada:")
    print("   python manage.py migrate connections --fake 0004")
    print("\n2. Reiniciar o servidor Django")
    print("\n3. Testar a configuração do Evolution API")
    print("=" * 60)

if __name__ == '__main__':
    try:
        fix_evolution_connection_table()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

