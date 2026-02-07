# Secretária: nome da assinatura (ex: Bia)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0009_secretary_prompt_and_model'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE ai_tenant_secretary_profile
            ADD COLUMN IF NOT EXISTS signature_name VARCHAR(100) NOT NULL DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE ai_tenant_secretary_profile DROP COLUMN IF EXISTS signature_name;
            """,
        ),
    ]
