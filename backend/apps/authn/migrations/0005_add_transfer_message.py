# Generated manually - 2025-01-XX
# ✅ ADD: transfer_message field to Department

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0004_add_performance_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Adicionar campo transfer_message se não existir
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'authn_department' 
                        AND column_name = 'transfer_message'
                    ) THEN
                        ALTER TABLE authn_department 
                        ADD COLUMN transfer_message TEXT NULL;
                    END IF;
                END $$;
            """,
            reverse_sql="""
                -- Reverter: remover campo se existir
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'authn_department' 
                        AND column_name = 'transfer_message'
                    ) THEN
                        ALTER TABLE authn_department 
                        DROP COLUMN transfer_message;
                    END IF;
                END $$;
            """
        ),
    ]

