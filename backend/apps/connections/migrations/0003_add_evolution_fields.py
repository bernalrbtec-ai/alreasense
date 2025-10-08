# Generated manually to fix migration issues

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('connections', '0002_add_tenant_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='evolutionconnection',
            name='base_url',
            field=models.URLField(help_text="URL base da Evolution API", null=True, blank=True),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='api_key',
            field=models.CharField(max_length=255, help_text="API Key da Evolution API", null=True, blank=True),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='webhook_url',
            field=models.URLField(help_text="URL do webhook para receber eventos", null=True, blank=True),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='status',
            field=models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive'), ('error', 'Error')], default='inactive'),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='last_check',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='evolutionconnection',
            name='last_error',
            field=models.TextField(blank=True, null=True),
        ),
    ]
