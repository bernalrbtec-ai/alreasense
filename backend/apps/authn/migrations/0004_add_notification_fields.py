# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0003_add_profile_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='notify_email',
            field=models.BooleanField(default=True, help_text='Receber notificações por e-mail'),
        ),
        migrations.AddField(
            model_name='user',
            name='notify_whatsapp',
            field=models.BooleanField(default=True, help_text='Receber notificações por WhatsApp'),
        ),
    ]
