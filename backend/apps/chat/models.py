"""
Models para o módulo Flow Chat.
Gerencia conversas, mensagens e anexos com suporte multi-tenant.
"""
import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

# Importar modelos de horários de atendimento
from .models_business_hours import BusinessHours, AfterHoursMessage, AfterHoursTaskConfig


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
        help_text='Nome da instância Evolution que recebeu a mensagem (UUID)'
    )
    instance_friendly_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Nome Amigável da Instância',
        help_text='Nome exibido para o usuário (ex: C_Financeiro)'
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
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Mensagem Apagada',
        help_text='True se mensagem foi apagada no WhatsApp'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Exclusão',
        help_text='Timestamp quando mensagem foi apagada'
    )
    is_edited = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Mensagem Editada',
        help_text='True se mensagem foi editada'
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
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
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
    
    # 🔗 Campos para cache inteligente (Redis 7 dias + S3 30 dias)
    media_hash = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        verbose_name='Hash de Mídia',
        help_text='Hash único para URL curta (/media/{hash})'
    )
    short_url = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='URL Curta',
        help_text='URL curta para Evolution API (evita URLs longas do S3)'
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
    transcription_quality = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('correct', 'Correta'),
            ('incorrect', 'Incorreta'),
        ],
        verbose_name='Qualidade da Transcrição',
        help_text='Feedback do usuário sobre a qualidade da transcrição'
    )
    transcription_quality_feedback_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Feedback de Qualidade em',
        help_text='Quando o usuário forneceu feedback de qualidade'
    )
    transcription_quality_feedback_by = models.ForeignKey(
        'authn.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transcription_quality_feedbacks',
        verbose_name='Feedback de Qualidade por',
        help_text='Usuário que forneceu feedback de qualidade'
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
    metadata = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name='Metadados',
        help_text='Dados extras (processing flags, media_type, etc)'
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
        """
        Define expires_at e gera media_hash/short_url automaticamente.
        """
        import logging
        from django.db import IntegrityError
        
        logger = logging.getLogger(__name__)
        
        # 1. Definir expires_at (cache local)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        # 2. Gerar media_hash e short_url se não existir
        if not self.media_hash:
            # ✅ IMPORTANTE: Gerar hash único evitando colisões
            max_attempts = 10  # Tentar até 10 vezes para evitar colisão
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    new_hash = self.generate_media_hash()
                    
                    # ✅ Verificar se hash já existe no banco (evitar IntegrityError)
                    from django.db import transaction
                    with transaction.atomic():
                        # Verificar se já existe outro attachment com esse hash
                        existing = MessageAttachment.objects.filter(media_hash=new_hash).exclude(id=self.id).exists()
                        
                        if not existing:
                            # Hash único, usar
                            self.media_hash = new_hash
                            logger.info(f"🔑 [ATTACHMENT] Hash gerado (tentativa {attempt + 1}): {self.media_hash}")
                            break
                        else:
                            logger.warning(f"⚠️ [ATTACHMENT] Hash colidiu: {new_hash} (tentativa {attempt + 1}/{max_attempts})")
                            attempt += 1
                            if attempt >= max_attempts:
                                # Se falhou muitas vezes, gerar hash mais longo (16 chars ao invés de 12)
                                import hashlib
                                import uuid
                                import time
                                unique_str = f"{uuid.uuid4().hex}{time.time()}{self.id if self.id else uuid.uuid4()}"
                                new_hash = hashlib.sha256(unique_str.encode()).hexdigest()[:16]
                                self.media_hash = new_hash
                                logger.warning(f"⚠️ [ATTACHMENT] Usando hash estendido (16 chars): {self.media_hash}")
                                break
                except IntegrityError:
                    # Se mesmo assim houver IntegrityError, tentar novamente
                    logger.warning(f"⚠️ [ATTACHMENT] IntegrityError ao gerar hash (tentativa {attempt + 1}/{max_attempts})")
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
            
            # Gerar short_url (endpoint está em /api/chat/media/)
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'https://alreasense-backend-production.up.railway.app')
            # Canonical com barra final
            self.short_url = f"{base_url}/api/chat/media/{self.media_hash}/"
            logger.info(f"🔗 [ATTACHMENT] URL curta gerada: {self.short_url}")
        
        # ✅ IMPORTANTE: Tentar salvar com tratamento de IntegrityError
        try:
            super().save(*args, **kwargs)
            logger.info(f"💾 [ATTACHMENT] Salvo no banco: ID={self.id}, hash={self.media_hash}")
        except IntegrityError as e:
            # ✅ Se IntegrityError por media_hash duplicado, regenerar e tentar novamente
            if 'media_hash' in str(e) or 'unique constraint' in str(e).lower():
                logger.warning(f"⚠️ [ATTACHMENT] IntegrityError por hash duplicado! Regenerando hash...")
                
                # Forçar regeneração de hash (mesmo que já tenha)
                old_hash = self.media_hash
                self.media_hash = None  # Forçar regeneração
                
                # Gerar novo hash (usando hash mais longo para garantir unicidade)
                import hashlib
                import uuid
                import time
                unique_str = f"{uuid.uuid4().hex}{time.time()}{self.id if self.id else uuid.uuid4()}"
                new_hash = hashlib.sha256(unique_str.encode()).hexdigest()[:16]  # 16 chars para maior segurança
                self.media_hash = new_hash
                self.short_url = f"{getattr(settings, 'BASE_URL', 'https://alreasense-backend-production.up.railway.app')}/api/chat/media/{self.media_hash}/"
                
                logger.info(f"🔄 [ATTACHMENT] Hash regenerado: {old_hash} → {self.media_hash}")
                
                # Tentar salvar novamente
                super().save(*args, **kwargs)
                logger.info(f"✅ [ATTACHMENT] Salvo com novo hash: ID={self.id}, hash={self.media_hash}")
            else:
                # Re-raise se for outro tipo de IntegrityError
                raise
    
    def generate_media_hash(self):
        """
        Gera hash único de 12 caracteres para URL curta.
        Formato: primeiros 12 chars do SHA256(uuid + timestamp)
        """
        import hashlib
        import uuid
        import time
        
        # UUID aleatório + timestamp para garantir unicidade
        unique_str = f"{uuid.uuid4().hex}{time.time()}"
        hash_hex = hashlib.sha256(unique_str.encode('utf-8')).hexdigest()
        
        # Retornar primeiros 12 caracteres (suficiente para unicidade)
        return hash_hex[:12]
    
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


class MessageReaction(models.Model):
    """
    Representa uma reação a uma mensagem (emoji).
    
    Attributes:
        message: Mensagem à qual a reação pertence
        user: Usuário que reagiu
        emoji: Emoji da reação (ex: 👍, ❤️, 😂)
        created_at: Timestamp da reação
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name='Mensagem'
    )
    user = models.ForeignKey(
        'authn.User',
        on_delete=models.CASCADE,
        related_name='message_reactions',
        verbose_name='Usuário',
        null=True,
        blank=True,
        help_text='NULL para reações de contatos externos (WhatsApp)'
    )
    external_sender = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Remetente Externo',
        help_text='Número do contato que reagiu (para reações recebidas do WhatsApp)'
    )
    emoji = models.CharField(
        max_length=10,
        verbose_name='Emoji',
        help_text='Emoji da reação (ex: 👍, ❤️, 😂)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Criado em'
    )
    
    class Meta:
        db_table = 'chat_message_reaction'
        verbose_name = 'Reação'
        verbose_name_plural = 'Reações'
        ordering = ['created_at']
        # ✅ UNIQUE: Um usuário/contato externo só pode reagir uma vez com cada emoji por mensagem
        # Se user existe, usa user; senão, usa external_sender
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'user', 'emoji'],
                condition=models.Q(user__isnull=False),
                name='unique_user_reaction_per_message_emoji'
            ),
            models.UniqueConstraint(
                fields=['message', 'external_sender', 'emoji'],
                condition=models.Q(external_sender__gt=''),
                name='unique_external_reaction_per_message_emoji'
            ),
        ]
        indexes = [
            models.Index(fields=['message', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} {self.emoji} em {self.message.id}"


class MessageEditHistory(models.Model):
    """
    Histórico de edições de mensagens.
    
    Armazena todas as versões anteriores do conteúdo de uma mensagem editada.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='edit_history',
        verbose_name='Mensagem'
    )
    old_content = models.TextField(
        verbose_name='Conteúdo Anterior',
        help_text='Conteúdo antes da edição'
    )
    new_content = models.TextField(
        verbose_name='Novo Conteúdo',
        help_text='Conteúdo após a edição'
    )
    edited_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Editado Por',
        help_text='Usuário que fez a edição'
    )
    edited_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Editado Em',
        db_index=True
    )
    evolution_message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='ID da Mensagem Evolution',
        help_text='ID da mensagem na Evolution API'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadados',
        help_text='Dados extras da edição'
    )
    
    class Meta:
        verbose_name = 'Histórico de Edição'
        verbose_name_plural = 'Históricos de Edições'
        ordering = ['-edited_at']
        indexes = [
            models.Index(fields=['message', '-edited_at']),
            models.Index(fields=['edited_by', '-edited_at']),
        ]
    
    def __str__(self):
        return f"Edição de {self.message.id} em {self.edited_at}"


class QuickReply(models.Model):
    """
    Respostas rápidas para uso no chat.
    Multi-tenant, isolado por tenant.
    """
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='quick_replies',
        verbose_name='Tenant'
    )
    title = models.CharField(
        max_length=100,
        verbose_name='Título',
        help_text="Título curto (ex: 'Boa tarde')"
    )
    content = models.TextField(
        verbose_name='Conteúdo',
        help_text="Conteúdo da resposta"
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Categoria',
        help_text="Categoria opcional"
    )
    use_count = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='Contador de Uso',
        help_text="Quantas vezes foi usada"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Ativa'
    )
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_quick_replies',
        verbose_name='Criado por'
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
        verbose_name = "Resposta Rápida"
        verbose_name_plural = "Respostas Rápidas"
        ordering = ['-use_count', 'title']  # Padrão: mais usadas primeiro, depois alfabética
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.tenant.name})"

