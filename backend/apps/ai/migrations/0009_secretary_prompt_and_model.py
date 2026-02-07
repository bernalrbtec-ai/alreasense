# Secretária: prompt no perfil e secretary_model nas settings

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0008_secretary_profile_and_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE ai_tenant_settings
            ADD COLUMN IF NOT EXISTS secretary_model VARCHAR(100) NOT NULL DEFAULT '';
            ALTER TABLE ai_tenant_secretary_profile
            ADD COLUMN IF NOT EXISTS prompt TEXT NOT NULL DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE ai_tenant_settings DROP COLUMN IF EXISTS secretary_model;
            ALTER TABLE ai_tenant_secretary_profile DROP COLUMN IF EXISTS prompt;
            """,
        ),
    ]
