"""
Management command to fix the Evolution Connection table structure.
Usage: python manage.py fix_evolution_table
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix the connections_evolutionconnection table structure'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.WARNING("🔧 CORRIGINDO TABELA connections_evolutionconnection"))
        self.stdout.write("=" * 60)
        
        with connection.cursor() as cursor:
            # 1. Verificar quais colunas existem
            self.stdout.write("\n1️⃣ Verificando colunas existentes...")
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'connections_evolutionconnection'
                AND table_schema = 'public';
            """)
            existing_columns = {row[0] for row in cursor.fetchall()}
            self.stdout.write(f"   Colunas encontradas: {', '.join(sorted(existing_columns))}")
            
            # 2. Remover colunas antigas se existirem
            self.stdout.write("\n2️⃣ Removendo colunas antigas...")
            old_columns = ['evo_token', 'evo_ws_url']
            for col in old_columns:
                if col in existing_columns:
                    try:
                        cursor.execute(f"""
                            ALTER TABLE connections_evolutionconnection 
                            DROP COLUMN IF EXISTS {col} CASCADE;
                        """)
                        self.stdout.write(self.style.SUCCESS(f"   ✅ Removida coluna: {col}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"   ⚠️  Erro ao remover {col}: {e}"))
                else:
                    self.stdout.write(f"   ⏭️  Coluna {col} não existe (OK)")
            
            # 3. Adicionar colunas novas se não existirem
            self.stdout.write("\n3️⃣ Adicionando colunas novas...")
            
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
                        self.stdout.write(self.style.SUCCESS(f"   ✅ Adicionada coluna: {col_name}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"   ⚠️  Erro ao adicionar {col_name}: {e}"))
                else:
                    self.stdout.write(f"   ⏭️  Coluna {col_name} já existe (OK)")
            
            # 4. Marcar migration como aplicada
            self.stdout.write("\n4️⃣ Marcando migration como aplicada...")
            try:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES ('connections', '0004_alter_evolutionconnection_options_and_more', NOW())
                    ON CONFLICT (app, name) DO NOTHING;
                """)
                self.stdout.write(self.style.SUCCESS("   ✅ Migration 0004 marcada como aplicada"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   ⚠️  Erro ao marcar migration: {e}"))
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ CORREÇÃO CONCLUÍDA!"))
        self.stdout.write("=" * 60)
        self.stdout.write("\nTabela connections_evolutionconnection corrigida com sucesso!")
        self.stdout.write("Agora você pode configurar o servidor Evolution API.")

