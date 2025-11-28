# Generated migration for adding deleted message fields

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0013_business_hours'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_deleted',
            field=models.BooleanField(default=False, db_index=True, verbose_name='Mensagem Apagada', help_text='True se mensagem foi apagada no WhatsApp'),
        ),
        migrations.AddField(
            model_name='message',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data de Exclusão', help_text='Timestamp quando mensagem foi apagada'),
        ),
    ]

