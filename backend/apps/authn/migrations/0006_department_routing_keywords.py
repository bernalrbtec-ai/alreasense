# Secretária IA: palavras-chave por departamento para roteamento
# RunSQL para não depender do modelo Department no estado (tabela foi criada via RunPython em 0003)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0005_add_transfer_message'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE authn_department
                ADD COLUMN IF NOT EXISTS routing_keywords JSONB NOT NULL DEFAULT '[]';
            """,
            reverse_sql="""
                ALTER TABLE authn_department
                DROP COLUMN IF EXISTS routing_keywords;
            """,
        ),
    ]
