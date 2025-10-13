# Generated manually to avoid User model conflict - Railway deploy fix

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0005_auto_20251013_1724'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='last_instance_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Nome da Última Instância'),
        ),
    ]
