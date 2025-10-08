# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
        ('connections', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='evolutionconnection',
            name='tenant',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='evolution_connections', to='tenancy.tenant'),
            preserve_default=False,
        ),
    ]
