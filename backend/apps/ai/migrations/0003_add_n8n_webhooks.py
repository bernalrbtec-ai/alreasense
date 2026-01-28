from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0002_tenant_ai_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantaisettings',
            name='n8n_audio_webhook_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='tenantaisettings',
            name='n8n_triage_webhook_url',
            field=models.URLField(blank=True),
        ),
        migrations.RemoveField(
            model_name='tenantaisettings',
            name='n8n_webhook_url',
        ),
    ]
