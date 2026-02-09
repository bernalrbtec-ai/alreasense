# Generated manually - usa RunSQL para evitar KeyError em chains com RunSQL anteriores
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0015_add_transcription_quality_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE chat_conversation 
            ADD COLUMN IF NOT EXISTS instance_friendly_name VARCHAR(100) NOT NULL DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE chat_conversation DROP COLUMN IF EXISTS instance_friendly_name;
            """,
        ),
    ]
