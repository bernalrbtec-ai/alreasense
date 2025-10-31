# Generated manually - Add metadata field to MessageAttachment
# Usando RunSQL porque a tabela foi criada via RunSQL na migration inicial
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0005_add_composite_indexes_FIXED'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Adicionar campo metadata ao chat_attachment
                ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS metadata JSONB NULL DEFAULT '{}';
            """,
            reverse_sql="""
                -- Reverter: remover campo metadata
                ALTER TABLE chat_attachment DROP COLUMN IF EXISTS metadata;
            """
        ),
    ]

