# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0004_add_composite_indexes_FIXED'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='notification_sent',
            field=models.BooleanField(db_index=True, default=False, help_text='Indica se a notificação foi enviada para os usuários', verbose_name='Notificação Enviada'),
        ),
    ]

