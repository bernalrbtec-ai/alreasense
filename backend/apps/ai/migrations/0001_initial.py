from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenancy', '0002_add_performance_indexes'),
        ('chat', '0014_add_message_deleted_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='AiKnowledgeDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200)),
                ('content', models.TextField()),
                ('source', models.CharField(blank=True, max_length=200)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('embedding', models.JSONField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='ai_knowledge_docs', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_knowledge_document',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'created_at'], name='ai_knowledg_tenant__c5e4a0_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AiMemoryItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('fact', 'Fato'), ('summary', 'Resumo'), ('action', 'Acao'), ('note', 'Nota')], default='fact', max_length=20)),
                ('content', models.TextField()),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('embedding', models.JSONField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='ai_memory_items', to='chat.conversation')),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='ai_memory_items', to='chat.message')),
                ('tenant', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='ai_memory_items', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_memory_item',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'created_at'], name='ai_memory__tenant__c5db2a_idx'),
                    models.Index(fields=['tenant', 'expires_at'], name='ai_memory__tenant__f357e2_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AiTriageResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(default='triage', max_length=50)),
                ('model_name', models.CharField(blank=True, max_length=100)),
                ('prompt_version', models.CharField(blank=True, max_length=100)),
                ('latency_ms', models.IntegerField(blank=True, null=True)),
                ('status', models.CharField(default='success', max_length=20)),
                ('result', models.JSONField(blank=True, default=dict)),
                ('raw_request', models.JSONField(blank=True, default=dict)),
                ('raw_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='ai_triage_results', to='chat.conversation')),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='ai_triage_results', to='chat.message')),
                ('tenant', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='ai_triage_results', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'ai_triage_result',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'created_at'], name='ai_triage__tenant__a85b95_idx'),
                    models.Index(fields=['conversation', 'created_at'], name='ai_triage__conver_92b266_idx'),
                    models.Index(fields=['message', 'created_at'], name='ai_triage__message_8d6c6b_idx'),
                ],
            },
        ),
    ]
