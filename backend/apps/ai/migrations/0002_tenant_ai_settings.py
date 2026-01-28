from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0001_initial'),
        ('tenancy', '0002_add_performance_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantAiSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ai_enabled', models.BooleanField(default=False)),
                ('audio_transcription_enabled', models.BooleanField(default=False)),
                ('transcription_auto', models.BooleanField(default=False)),
                ('transcription_min_seconds', models.IntegerField(default=5)),
                ('transcription_max_mb', models.IntegerField(default=16)),
                ('triage_enabled', models.BooleanField(default=False)),
                ('agent_model', models.CharField(default='llama3.1:8b', max_length=100)),
                ('n8n_webhook_url', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ai_settings', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_tenant_settings',
            },
        ),
    ]
