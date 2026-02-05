from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0005_add_n8n_ai_webhook'),
    ]

    operations = [
        migrations.CreateModel(
            name='AiGatewayAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conversation_id', models.UUIDField(blank=True, null=True)),
                ('message_id', models.UUIDField(blank=True, null=True)),
                ('contact_id', models.UUIDField(blank=True, null=True)),
                ('department_id', models.UUIDField(blank=True, null=True)),
                ('agent_id', models.UUIDField(blank=True, null=True)),
                ('request_id', models.UUIDField()),
                ('trace_id', models.UUIDField()),
                ('status', models.CharField(default='success', max_length=20)),
                ('model_name', models.CharField(blank=True, max_length=100)),
                ('latency_ms', models.IntegerField(blank=True, null=True)),
                ('rag_hits', models.IntegerField(blank=True, null=True)),
                ('prompt_version', models.CharField(blank=True, max_length=100)),
                ('input_summary', models.TextField(blank=True)),
                ('output_summary', models.TextField(blank=True)),
                ('handoff', models.BooleanField(default=False)),
                ('handoff_reason', models.CharField(blank=True, max_length=100)),
                ('error_code', models.CharField(blank=True, max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('request_payload_masked', models.JSONField(blank=True, default=dict)),
                ('response_payload_masked', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_gateway_audits', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_gateway_audit',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='aigatewayaudit',
            index=models.Index(fields=['tenant', 'created_at'], name='ai_gateway_tenant__f9fc5a_idx'),
        ),
        migrations.AddIndex(
            model_name='aigatewayaudit',
            index=models.Index(fields=['request_id'], name='ai_gateway_request_7f5b4e_idx'),
        ),
        migrations.AddIndex(
            model_name='aigatewayaudit',
            index=models.Index(fields=['trace_id'], name='ai_gateway_trace_13c9a9_idx'),
        ),
        migrations.AddIndex(
            model_name='aigatewayaudit',
            index=models.Index(fields=['conversation_id', 'created_at'], name='ai_gateway_conver_4f41f0_idx'),
        ),
        migrations.AddIndex(
            model_name='aigatewayaudit',
            index=models.Index(fields=['message_id', 'created_at'], name='ai_gateway_message_1d6b5f_idx'),
        ),
    ]
