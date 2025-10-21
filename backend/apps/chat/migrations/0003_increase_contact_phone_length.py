# Generated manually by Paulo Bernal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_add_group_support'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE chat_conversation
            ALTER COLUMN contact_phone TYPE VARCHAR(50);
            """,
            reverse_sql="""
            ALTER TABLE chat_conversation
            ALTER COLUMN contact_phone TYPE VARCHAR(20);
            """
        ),
    ]

