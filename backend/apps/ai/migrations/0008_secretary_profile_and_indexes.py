# Secretária IA: TenantSecretaryProfile, secretary_enabled, índices RAG/memória

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
        ('ai', '0007_add_quality_latency_model_fields'),
    ]

    operations = [
        # secretary_enabled em TenantAiSettings
        migrations.AddField(
            model_name='tenantaisettings',
            name='secretary_enabled',
            field=models.BooleanField(default=False, help_text='Ativar secretária IA no Inbox (responde e opcionalmente encaminha por departamento)'),
        ),
        # TenantSecretaryProfile
        migrations.CreateModel(
            name='TenantSecretaryProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('form_data', models.JSONField(blank=True, default=dict, help_text='Dados da empresa: missão, endereço, telefone, serviços, etc. Usado como contexto RAG (source=secretary).')),
                ('use_memory', models.BooleanField(default=True, help_text='Usar memória de conversas anteriores por contato (últimos 12 meses). Desativar para LGPD.')),
                ('is_active', models.BooleanField(default=False, help_text='Perfil ativo (dados prontos para RAG). Ativar no Inbox é controlado por TenantAiSettings.secretary_enabled.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='secretary_profile', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_tenant_secretary_profile',
            },
        ),
        # Índice (tenant, source) em AiKnowledgeDocument
        migrations.AddIndex(
            model_name='aiknowledgedocument',
            index=models.Index(fields=['tenant', 'source'], name='ai_knowledge_tenant_source'),
        ),
        # Índice (tenant, conversation_id, created_at) em AiMemoryItem
        migrations.AddIndex(
            model_name='aimemoryitem',
            index=models.Index(fields=['tenant', 'conversation_id', 'created_at'], name='ai_memory_tenant_conv_created'),
        ),
    ]
