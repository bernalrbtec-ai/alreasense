from django.db import models

from apps.tenancy.models import Tenant


class AiKnowledgeDocument(models.Model):
    """Documento base para RAG por tenant."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ai_knowledge_docs')
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    source = models.CharField(max_length=200, blank=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    embedding = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_knowledge_document'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title or self.content[:40]}..."


class AiMemoryItem(models.Model):
    """Memória de conversas por tenant."""

    KIND_CHOICES = [
        ('fact', 'Fato'),
        ('summary', 'Resumo'),
        ('action', 'Acao'),
        ('note', 'Nota'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ai_memory_items')
    conversation_id = models.UUIDField(null=True, blank=True)
    message_id = models.UUIDField(null=True, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='fact')
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_memory_item'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'expires_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.kind}: {self.content[:40]}..."


class AiTriageResult(models.Model):
    """Resultado de triagem vindo do N8N/LLM."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ai_triage_results')
    conversation_id = models.UUIDField(null=True, blank=True)
    message_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=50, default='triage')
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=100, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default='success')
    result = models.JSONField(default=dict, blank=True)
    raw_request = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_triage_result'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['conversation_id', 'created_at']),
            models.Index(fields=['message_id', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} ({self.status})"


class TenantAiSettings(models.Model):
    """Configurações de IA por tenant."""

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='ai_settings',
    )
    ai_enabled = models.BooleanField(default=False)
    audio_transcription_enabled = models.BooleanField(default=False)
    transcription_auto = models.BooleanField(default=False)
    transcription_min_seconds = models.IntegerField(default=5)
    transcription_max_mb = models.IntegerField(default=16)
    triage_enabled = models.BooleanField(default=False)
    agent_model = models.CharField(max_length=100, default='llama3.1:8b')
    n8n_audio_webhook_url = models.URLField(blank=True)
    n8n_triage_webhook_url = models.URLField(blank=True)
    n8n_models_webhook_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_tenant_settings'

    def __str__(self):
        return f"AI Settings ({self.tenant_id})"
