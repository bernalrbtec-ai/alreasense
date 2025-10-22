"""
Models para o módulo Flow Chat.
Gerencia conversas, mensagens e anexos com suporte multi-tenant.
"""
import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta


class Conversation(models.Model):
    """
    Representa uma conversa entre o tenant e um contato.
    
    Attributes:
        tenant: Tenant dono da conversa
        department: Departamento responsável
        contact_phone: Telefone do contato (formato E.164)
        contact_name: Nome do contato
        assigned_to: Usuário responsável pela conversa
        status: Status da conversa (open/closed)
        last_message_at: Timestamp da última mensagem
        metadata: Dados extras da Evolution API (JSON)
        participants: Usuários que participam da conversa
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendente (Inbox)'),
        ('open', 'Aberta'),
        ('closed', 'Fechada'),
    ]
    
    TYPE_CHOICES = [
        ('individual', 'Individual (1:1)'),
        ('group', 'Grupo do WhatsApp'),
        ('broadcast', 'Lista de Transmissão'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name='Tenant'
    )
    department = models.ForeignKey(
        'authn.Department',
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name='Departamento',
        null=True,
        blank=True,
        help_text='Null = Conversa pendente no Inbox'
    )
    contact_phone = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name='Telefone do Contato',
        help_text='Formato E.164 ou Group ID: +5517999999999 ou +5517999999999-1234567890'
    )
    contact_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nome do Contato'
    )
    profile_pic_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Foto de Perfil',
        help_text='URL da foto de perfil do WhatsApp'
    )
    instance_name = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Instância de Origem',
        help_text='Nome da instância Evolution que recebeu a mensagem (ex: Comercial, Suporte)'
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='individual',
        db_index=True,
        verbose_name='Tipo de Conversa',
        help_text='Individual (1:1), Grupo ou Lista de Transmissão'
    )
    group_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadados do Grupo',
        help_text='Nome, foto, participantes, etc (apenas para grupos)'
    )
    assigned_to = models.ForeignKey(
        'authn.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_conversations',
        verbose_name='Responsável'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True,
        verbose_name='Status'
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Última Mensagem'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadados',
        help_text='Dados extras da Evolution API'
    )
    participants = models.ManyToManyField(
        'authn.User',
        related_name='conversations',
        blank=True,
        verbose_name='Participantes'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    
    class Meta:
        db_table = 'chat_conversation'
        verbose_name = 'Conversa'
        verbose_name_plural = 'Conversas'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'department', 'status']),
            models.Index(fields=['tenant', 'contact_phone']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.contact_name or self.contact_phone} - {self.tenant.name}"
    
    def update_last_message(self):
        """Atualiza o timestamp da última mensagem."""
        self.last_message_at = timezone.now()
        self.save(update_fields=['last_message_at'])
    
    @property
    def unread_count(self):
        """Conta mensagens não lidas (incoming que não estão 'seen')."""
        return self.messages.filter(
            direction='incoming',
            status__in=['sent', 'delivered']
        ).count()


class Message(models.Model):
    """
    Representa uma mensagem dentro de uma conversa.
    
    Attributes:
        conversation: Conversa à qual a mensagem pertence
        sender: Usuário que enviou (None se incoming)
        content: Conteúdo textual da mensagem
        direction: incoming (recebida) ou outgoing (enviada)
        message_id: ID único da Evolution API (para idempotência)
        evolution_status: Status raw da Evolution
        error_message: Mensagem de erro se falhar
        status: sent/delivered/seen
        is_internal: Se é nota interna (não vai para WhatsApp)
    """
    
    DIRECTION_CHOICES = [
        ('incoming', 'Recebida'),
        ('outgoing', 'Enviada'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregue'),
        ('seen', 'Vista'),
        ('failed', 'Falhou'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Conversa'
    )
    sender = models.ForeignKey(
        'authn.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Remetente',
        help_text='NULL para mensagens incoming'
    )
    sender_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Nome do Remetente',
        help_text='Nome de quem enviou (para grupos WhatsApp)'
    )
    sender_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Telefone do Remetente',
        help_text='Telefone de quem enviou (para grupos WhatsApp)'
    )
    content = models.TextField(
        blank=True,
        verbose_name='Conteúdo'
    )
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        db_index=True,
        verbose_name='Direção'
    )
    message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        unique=True,
        verbose_name='ID da Evolution',
        help_text='ID único para idempotência'
    )
    evolution_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Status Evolution',
        help_text='Status raw da API Evolution'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Erro',
        help_text='Mensagem de erro se falhar'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Status'
    )
    is_internal = models.BooleanField(
        default=False,
        verbose_name='Nota Interna',
        help_text='Notas internas não são enviadas para WhatsApp'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadados',
        help_text='Dados extras (attachment_urls, etc)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Criado em'
    )
    
    class Meta:
        db_table = 'chat_message'
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['message_id']),
            models.Index(fields=['status', 'direction']),
        ]
    
    def __str__(self):
        direction_symbol = "📩" if self.direction == 'incoming' else "📨"
        return f"{direction_symbol} {self.conversation.contact_phone} - {self.created_at.strftime('%d/%m %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Atualiza last_message_at da conversa ao salvar."""
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new and not self.is_internal:
            self.conversation.update_last_message()


class MessageAttachment(models.Model):
    """
    Representa um anexo de mensagem (imagem, vídeo, documento, áudio).
    
    Attributes:
        message: Mensagem à qual o anexo pertence
        tenant: Tenant (para organização de storage)
        original_filename: Nome original do arquivo
        mime_type: Tipo MIME (image/jpeg, video/mp4, etc)
        file_path: Caminho no storage local
        file_url: URL de acesso (presigned ou local)
        thumbnail_path: Caminho da thumbnail (imagens/vídeos)
        storage_type: local (Railway Volume) ou s3 (MinIO)
        size_bytes: Tamanho em bytes
        expires_at: Data de expiração (cache local)
    """
    
    STORAGE_CHOICES = [
        ('local', 'Local'),
        ('s3', 'S3'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Mensagem'
    )
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='chat_attachments',
        verbose_name='Tenant'
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name='Nome Original'
    )
    mime_type = models.CharField(
        max_length=100,
        verbose_name='Tipo MIME'
    )
    file_path = models.CharField(
        max_length=500,
        verbose_name='Caminho do Arquivo'
    )
    file_url = models.TextField(
        verbose_name='URL de Acesso (pode ser longa: presigned URLs S3)'
    )
    thumbnail_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Caminho da Thumbnail',
        help_text='Miniatura para imagens/vídeos'
    )
    storage_type = models.CharField(
        max_length=10,
        choices=STORAGE_CHOICES,
        default='local',
        db_index=True,
        verbose_name='Tipo de Armazenamento'
    )
    size_bytes = models.BigIntegerField(
        default=0,
        verbose_name='Tamanho (bytes)'
    )
    expires_at = models.DateTimeField(
        verbose_name='Expira em',
        help_text='Cache local expira após 7 dias'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    
    # ✨ Campos para IA (Flow AI addon)
    transcription = models.TextField(
        null=True,
        blank=True,
        verbose_name='Transcrição',
        help_text='Transcrição de áudio (se aplicável)'
    )
    transcription_language = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name='Idioma da Transcrição',
        help_text='Código do idioma (pt-BR, en-US, etc)'
    )
    ai_summary = models.TextField(
        null=True,
        blank=True,
        verbose_name='Resumo IA',
        help_text='Resumo gerado pela IA'
    )
    ai_tags = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Tags IA',
        help_text='Tags extraídas pela IA'
    )
    ai_sentiment = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('positive', 'Positivo'),
            ('neutral', 'Neutro'),
            ('negative', 'Negativo'),
        ],
        verbose_name='Sentimento',
        help_text='Análise de sentimento pela IA'
    )
    ai_metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Metadados IA',
        help_text='Dados adicionais da IA (ações, entidades, etc)'
    )
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendente'),
            ('processing', 'Processando'),
            ('completed', 'Concluído'),
            ('failed', 'Falhou'),
            ('skipped', 'Ignorado'),
        ],
        default='pending',
        db_index=True,
        verbose_name='Status de Processamento',
        help_text='Status do processamento de IA'
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Processado em',
        help_text='Quando foi processado pela IA'
    )
    
    class Meta:
        db_table = 'chat_attachment'
        verbose_name = 'Anexo'
        verbose_name_plural = 'Anexos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'storage_type']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} ({self.get_storage_type_display()})"
    
    def save(self, *args, **kwargs):
        """Define expires_at automaticamente se não setado."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Verifica se o arquivo local expirou."""
        return timezone.now() > self.expires_at
    
    @property
    def is_image(self):
        """Verifica se é uma imagem."""
        return self.mime_type.startswith('image/')
    
    @property
    def is_video(self):
        """Verifica se é um vídeo."""
        return self.mime_type.startswith('video/')
    
    @property
    def is_audio(self):
        """Verifica se é um áudio."""
        return self.mime_type.startswith('audio/')
    
    @property
    def is_document(self):
        """Verifica se é um documento."""
        return self.mime_type.startswith('application/')

