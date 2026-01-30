from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0003_add_n8n_webhooks'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantaisettings',
            name='n8n_models_webhook_url',
            field=models.URLField(blank=True),
        ),
    ]
