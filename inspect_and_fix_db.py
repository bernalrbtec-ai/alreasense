"""
Script para inspecionar e corrigir o banco PostgreSQL da Railway
"""
import psycopg2
import sys

# Railway PostgreSQL connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def main():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("=" * 80)
        print("🔍 INSPEÇÃO DO BANCO DE DADOS RAILWAY")
        print("=" * 80)
        
        # 1. Verificar estrutura da tabela django_migrations
        print("\n1️⃣ Estrutura da tabela django_migrations:")
        print("-" * 80)
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'django_migrations'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"   {col[0]:<20} | {col[1]:<20} | nullable={col[2]}")
        
        # 2. Verificar constraints/índices
        print("\n2️⃣ Constraints da tabela django_migrations:")
        print("-" * 80)
        cur.execute("""
            SELECT conname, contype
            FROM pg_constraint
            WHERE conrelid = 'django_migrations'::regclass;
        """)
        constraints = cur.fetchall()
        if constraints:
            for const in constraints:
                print(f"   {const[0]:<40} | tipo={const[1]}")
        else:
            print("   ❌ NENHUMA CONSTRAINT ENCONTRADA!")
        
        # 3. Verificar colunas da tabela contacts_contact
        print("\n3️⃣ Colunas da tabela contacts_contact:")
        print("-" * 80)
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'contacts_contact'
            ORDER BY ordinal_position;
        """)
        contact_columns = cur.fetchall()
        has_lifecycle = False
        for col in contact_columns:
            if col[0] == 'lifecycle_stage':
                has_lifecycle = True
            print(f"   ✅ {col[0]}")
        
        if has_lifecycle:
            print("\n   ⚠️  ENCONTRADA COLUNA 'lifecycle_stage' - NÃO DEVERIA EXISTIR!")
        else:
            print("\n   ✅ Coluna 'lifecycle_stage' NÃO existe (correto - é @property)")
        
        # 4. Verificar índices existentes para contacts_contact
        print("\n4️⃣ Índices existentes para contacts_contact:")
        print("-" * 80)
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'contacts_contact'
            AND indexname LIKE 'idx_%';
        """)
        indexes = cur.fetchall()
        if indexes:
            for idx in indexes:
                print(f"   ✅ {idx[0]}")
                print(f"      {idx[1]}")
        else:
            print("   ℹ️  Nenhum índice customizado (idx_*) encontrado ainda")
        
        # 5. Verificar migrations aplicadas
        print("\n5️⃣ Últimas 10 migrations aplicadas:")
        print("-" * 80)
        cur.execute("""
            SELECT app, name, applied
            FROM django_migrations
            ORDER BY applied DESC
            LIMIT 10;
        """)
        migrations = cur.fetchall()
        for mig in migrations:
            print(f"   {mig[0]:<20} | {mig[1]:<50} | {mig[2]}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print("✅ INSPEÇÃO CONCLUÍDA!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

