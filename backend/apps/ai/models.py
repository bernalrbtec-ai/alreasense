import hashlib
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

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
            models.Index(fields=['tenant', 'source'], name='ai_knowledge_tenant_source'),
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
            models.Index(fields=['tenant', 'conversation_id', 'created_at'], name='ai_memory_tenant_conv_created'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.kind}: {self.content[:40]}..."


class ConversationSummary(models.Model):
    """
    Resumo de conversa para gestão RAG (Sense). Status pending/approved/rejected.
    Aprovados são enviados ao pgvector (n8n) via rag-upsert; Bia consulta o pgvector.
    Tabela criada via script SQL (docs/SQL_conversation_summary.sql); managed=False.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_REJECTED, "Reprovado"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="conversation_summaries")
    conversation_id = models.UUIDField(db_index=True)
    contact_phone = models.CharField(max_length=64, default="")
    contact_name = models.CharField(max_length=255, default="")
    content = models.TextField(default="")
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_conversation_summaries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_conversation_summary"
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "conversation_id"],
                name="uniq_ai_conversation_summary_tenant_conversation",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Summary {self.conversation_id} ({self.status})"


class ConsolidationRecord(models.Model):
    """
    Um RAG por contato. Registro de resumos consolidados (job diário ou manual).
    Um registro por (tenant, contact_phone). summary_ids = lista de PKs de ConversationSummary.
    Refresh = UPDATE summary_ids + re-upsert no RAG com mesmo consolidated_id.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="consolidation_records")
    contact_phone = models.CharField(max_length=64, default="")
    consolidated_id = models.UUIDField(unique=False)  # unique per (tenant, contact_phone) via constraint
    summary_ids = models.JSONField(default=list, blank=True)  # list of ConversationSummary.id
    content = models.TextField(blank=True, default="")  # cache do texto consolidado para exibição na UI
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_consolidation_record"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "consolidated_id"],
                name="uniq_ai_consolidation_record_tenant_consolidated",
            ),
            models.UniqueConstraint(
                fields=["tenant", "contact_phone"],
                name="uniq_ai_consolidation_record_tenant_contact",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Consolidation {self.contact_phone} ({self.tenant_id})"


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


class AiGatewayAudit(models.Model):
    """Auditoria de chamadas do Gateway IA (inclui testes)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ai_gateway_audits')
    conversation_id = models.UUIDField(null=True, blank=True)
    message_id = models.UUIDField(null=True, blank=True)
    contact_id = models.UUIDField(null=True, blank=True)
    department_id = models.UUIDField(null=True, blank=True)
    agent_id = models.UUIDField(null=True, blank=True)
    request_id = models.UUIDField()
    trace_id = models.UUIDField()
    status = models.CharField(max_length=20, default='success')
    model_name = models.CharField(max_length=100, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    rag_hits = models.IntegerField(null=True, blank=True)
    prompt_version = models.CharField(max_length=100, blank=True)
    input_summary = models.TextField(blank=True)
    output_summary = models.TextField(blank=True)
    handoff = models.BooleanField(default=False)
    handoff_reason = models.CharField(max_length=100, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    request_payload_masked = models.JSONField(default=dict, blank=True)
    response_payload_masked = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # BIA: tokens e tipo de agente (preenchidos quando n8n envia meta.input_tokens / meta.output_tokens)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    agent_type = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'ai_gateway_audit'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'agent_type', 'created_at']),
            models.Index(fields=['request_id']),
            models.Index(fields=['trace_id']),
            models.Index(fields=['conversation_id', 'created_at']),
            models.Index(fields=['message_id', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Gateway audit ({self.status})"


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
    secretary_enabled = models.BooleanField(
        default=False,
        help_text='Ativar secretária IA no Inbox (responde e opcionalmente encaminha por departamento)',
    )
    secretary_model = models.CharField(
        max_length=100,
        blank=True,
        help_text='Modelo usado pela Secretária IA (ex: qwen2.5:7b-instruct). Vazio = usa o modelo padrão (agent_model).',
    )
    agent_model = models.CharField(max_length=100, default='llama3.1:8b')
    n8n_audio_webhook_url = models.URLField(blank=True)
    n8n_triage_webhook_url = models.URLField(blank=True)
    n8n_ai_webhook_url = models.URLField(blank=True)
    n8n_models_webhook_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_tenant_settings'

    def __str__(self):
        return f"AI Settings ({self.tenant_id})"


class TenantSecretaryProfile(models.Model):
    """
    Perfil da Secretária IA por tenant: dados da empresa (form_data) para RAG,
    opção de memória por contato (1 ano) e estado ativo.
    """

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='secretary_profile',
    )
    form_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dados da empresa: missão, endereço, telefone, serviços, etc. Usado como contexto RAG (source=secretary).',
    )
    prompt = models.TextField(
        blank=True,
        help_text='Prompt de sistema da secretária (ex: instruções, tom, regras). Se vazio, o N8N usa o padrão do fluxo.',
    )
    signature_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='Nome exibido nas mensagens da secretária (ex: Bia). Se vazio, usa "Assistente".',
    )
    use_memory = models.BooleanField(
        default=True,
        help_text='Usar memória de conversas anteriores por contato (últimos 12 meses). Desativar para LGPD.',
    )
    is_active = models.BooleanField(
        default=False,
        help_text='Perfil ativo (dados prontos para RAG). Ativar no Inbox é controlado por TenantAiSettings.secretary_enabled.',
    )
    inbox_idle_minutes = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text='Minutos sem interação no Inbox para fechar conversa (0=desativado, máx. 1440=24h).',
    )
    response_delay_seconds = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text='Segundos para aguardar antes de responder na primeira interação; se o cliente enviar mais mensagens nesse período, o tempo é reiniciado e a resposta é única. Após a primeira resposta, as demais são imediatas. 0 = sempre responder na hora.',
    )
    summary_auto_approve_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Config de aprovação automática de resumos RAG: enabled, criteria (min_words, max_words, etc.).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_tenant_secretary_profile'

    def __str__(self):
        return f"Secretary profile ({self.tenant_id})"


class AiTranscriptionDailyMetric(models.Model):
    """Métricas diárias de transcrição por tenant (UTC)."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="ai_transcription_daily_metrics",
    )
    date = models.DateField()
    minutes_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    audio_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    quality_correct_count = models.IntegerField(default=0)
    quality_incorrect_count = models.IntegerField(default=0)
    quality_unrated_count = models.IntegerField(default=0)
    avg_latency_ms = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    models_used = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_transcription_daily_metrics"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "date"], name="uniq_ai_transcription_daily_tenant_date"),
        ]

    def __str__(self):
        return f"Transcription metrics ({self.tenant_id}) {self.date}"


class MessageEmbedding(models.Model):
    """
    Cache de embeddings de mensagens para evitar recalcular embeddings do mesmo texto.
    Usa hash SHA256 do texto normalizado como chave única.
    """

    text_hash = models.CharField(
        max_length=64,
        db_index=True,
        unique=True,
        help_text="SHA256 hash do texto normalizado (lowercase, strip)"
    )
    text = models.TextField(
        help_text="Texto original (para debug/verificação)"
    )
    embedding = models.JSONField(
        help_text="Embedding vetorial (lista de floats)"
    )
    hit_count = models.IntegerField(
        default=0,
        help_text="Quantas vezes este embedding foi usado (cache hits)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(
        auto_now=True,
        help_text="Última vez que este embedding foi usado"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data de expiração (opcional, para limpeza automática)"
    )

    class Meta:
        db_table = "ai_message_embedding"
        indexes = [
            models.Index(fields=["text_hash"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-last_used_at"]

    def __str__(self):
        return f"Embedding: {self.text[:40]}... (hits: {self.hit_count})"

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normaliza texto para gerar hash consistente."""
        if not text:
            return ""
        return text.strip().lower()

    @staticmethod
    def get_text_hash(text: str) -> str:
        """Gera hash SHA256 do texto normalizado."""
        normalized = MessageEmbedding.normalize_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def get_or_create_embedding(cls, text: str, embedding_func):
        """
        Busca embedding no cache ou cria novo usando embedding_func.
        
        Args:
            text: Texto para gerar embedding
            embedding_func: Função que gera embedding (ex: embed_text)
        
        Returns:
            tuple: (embedding, was_cached)
        """
        if not text or not text.strip():
            return [], False

        text_hash = cls.get_text_hash(text)
        
        # Tentar buscar no cache
        cached = cls.objects.filter(text_hash=text_hash).first()
        if cached:
            # Atualizar contadores
            cached.hit_count += 1
            cached.last_used_at = timezone.now()
            cached.save(update_fields=["hit_count", "last_used_at"])
            return cached.embedding, True
        
        # Gerar novo embedding
        embedding = embedding_func(text)
        if not embedding:
            return [], False
        
        # Salvar no cache
        try:
            cls.objects.create(
                text_hash=text_hash,
                text=text[:1000],  # Limitar tamanho para não exceder limites
                embedding=embedding,
                hit_count=1,
            )
        except Exception:
            # Se falhar (ex: race condition), tentar buscar novamente
            cached = cls.objects.filter(text_hash=text_hash).first()
            if cached:
                cached.hit_count += 1
                cached.last_used_at = timezone.now()
                cached.save(update_fields=["hit_count", "last_used_at"])
                return cached.embedding, True
        
        return embedding, False
