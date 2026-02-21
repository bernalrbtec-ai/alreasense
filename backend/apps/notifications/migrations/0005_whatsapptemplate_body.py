# Add body field to WhatsAppTemplate (texto do template para exibição no chat)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_add_whatsapp_template'),
    ]

    operations = [
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
    ]
