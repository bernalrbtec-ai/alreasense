# Add buttons field to WhatsAppTemplate (botões quick_reply etc. do sync Meta)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_whatsapptemplate_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsapptemplate',
            name='buttons',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Lista de botões (ex.: quick_reply) extraída da API Meta (components type BUTTONS).',
                verbose_name='Botões',
            ),
        ),
    ]
