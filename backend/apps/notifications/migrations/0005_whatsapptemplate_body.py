# Add body field to WhatsAppTemplate (texto do template para exibição no chat)
# Idempotente: se a coluna já existir (ex.: adicionada manualmente), não falha.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_add_whatsapp_template'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='whatsapptemplate',
                    name='body',
                    field=models.TextField(
                        blank=True,
                        default='',
                        help_text='Corpo do template com placeholders {{1}}, {{2}}, etc. (extraído da API Meta).',
                        verbose_name='Texto do body',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE notifications_whatsapp_template
                        ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT '';
                    """,
                    reverse_sql="""
                        ALTER TABLE notifications_whatsapp_template
                        DROP COLUMN IF EXISTS body;
                    """,
                ),
            ],
        ),
    ]
