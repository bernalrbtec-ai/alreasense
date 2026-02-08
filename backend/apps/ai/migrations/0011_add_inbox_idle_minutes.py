# Secretária: tempo máximo no Inbox sem interação (fechar por falta de comunicação)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0010_secretary_signature_name'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE ai_tenant_secretary_profile
            ADD COLUMN IF NOT EXISTS inbox_idle_minutes INTEGER NOT NULL DEFAULT 0;
            """,
            reverse_sql="""
            ALTER TABLE ai_tenant_secretary_profile DROP COLUMN IF EXISTS inbox_idle_minutes;
            """,
        ),
    ]
