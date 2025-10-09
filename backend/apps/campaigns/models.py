from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid


class Campaign(models.Model):
    """Campanha de disparo em massa"""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativa'
        PAUSED = 'paused', 'Pausada'
        COMPLETED = 'completed', 'Concluída'
        CANCELLED = 'cancelled', 'Cancelada'
    
    class ScheduleType(models.TextChoices):
        IMMEDIATE = 'immediate', 'Imediato'
        BUSINESS_DAYS = 'business_days', 'Apenas Dias Úteis'
        BUSINESS_HOURS = 'business_hours', 'Horário Comercial'
        CUSTOM_PERIOD = 'custom_period', 'Período Personalizado'
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='campaigns'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    is_paused = models.BooleanField(default=False, db_index=True)
    
    # Relacionamentos
    instance = models.ForeignKey(
        'notifications.WhatsAppInstance',
        on_delete=models.PROTECT,
        related_name='campaigns'
    )
    
    # Agendamento
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.IMMEDIATE
    )
    morning_start = models.TimeField(null=True, blank=True)
    morning_end = models.TimeField(null=True, blank=True)
    afternoon_start = models.TimeField(null=True, blank=True)
    afternoon_end = models.TimeField(null=True, blank=True)
    skip_weekends = models.BooleanField(default=True)
    skip_holidays = models.BooleanField(default=True)
    
    # Contadores
    total_contacts = models.IntegerField(default=0)
    current_contact_index = models.IntegerField(default=0)
    sent_messages = models.IntegerField(default=0)
    failed_messages = models.IntegerField(default=0)
    responded_count = models.IntegerField(default=0)
    
    # Controle
    next_scheduled_send = models.DateTimeField(null=True, blank=True, db_index=True)
    last_send_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    is_processing = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Auditoria
    created_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='campaigns_created'
    )
    started_by = models.ForeignKey(
        'authn.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns_started'
    )
    
    # Erro tracking
    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    auto_pause_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'campaigns_campaign'
        verbose_name = 'Campanha'
        verbose_name_plural = 'Campanhas'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['tenant', 'status', 'created_at']),
            models.Index(fields=['status', 'is_paused', 'next_scheduled_send']),
            models.Index(fields=['instance', 'status']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['instance'],
                condition=models.Q(status='active'),
                name='unique_active_campaign_per_instance'
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) - {self.tenant.name}"
    
    @property
    def progress_percentage(self):
        if self.total_contacts == 0:
            return 0
        return round((self.sent_messages / self.total_contacts) * 100, 1)
    
    @property
    def response_rate(self):
        if self.sent_messages == 0:
            return 0
        return round((self.responded_count / self.sent_messages) * 100, 1)
    
    @property
    def can_be_started(self):
        return (
            self.status == self.Status.DRAFT and
            self.total_contacts > 0 and
            self.messages.filter(is_active=True).exists() and
            self.instance.connection_state == 'open'
        )
    
    def start(self, user):
        if not self.can_be_started:
            raise ValidationError("Campanha não pode ser iniciada")
        
        self.status = self.Status.ACTIVE
        self.is_paused = False
        self.started_at = timezone.now()
        self.started_by = user
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.save(update_fields=['status', 'is_paused', 'started_at', 'started_by', 'next_scheduled_send'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_started',
            message=f'Campanha iniciada por {user.email}',
            metadata={'total_contacts': self.total_contacts}
        )
    
    def pause(self, user, reason=''):
        self.is_paused = True
        self.paused_at = timezone.now()
        self.save(update_fields=['is_paused', 'paused_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.WARNING,
            event_type='campaign_paused',
            message=f'Campanha pausada por {user.email}',
            metadata={'reason': reason}
        )
    
    def resume(self, user):
        self.is_paused = False
        self.resumed_at = timezone.now()
        self.next_scheduled_send = timezone.now() + timezone.timedelta(seconds=10)
        self.auto_pause_reason = ''
        self.save(update_fields=['is_paused', 'resumed_at', 'next_scheduled_send', 'auto_pause_reason'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.INFO,
            event_type='campaign_resumed',
            message=f'Campanha retomada por {user.email}'
        )
    
    def cancel(self, user, reason=''):
        self.status = self.Status.CANCELLED
        self.is_paused = True
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'is_paused', 'cancelled_at'])
        
        CampaignLog.objects.create(
            campaign=self,
            user=user,
            level=CampaignLog.Level.ERROR,
            event_type='campaign_cancelled',
            message=f'Campanha cancelada por {user.email}',
            metadata={'reason': reason, 'sent_messages': self.sent_messages}
        )


class CampaignMessage(models.Model):
    """Mensagem de campanha (até 5 por campanha)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='messages')
    
    message_text = models.TextField()
    order = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    is_active = models.BooleanField(default=True)
    
    # Métricas
    times_sent = models.IntegerField(default=0)
    response_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_message'
        ordering = ['campaign', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'order'],
                name='unique_message_order_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"Mensagem {self.order} - {self.campaign.name}"
    
    @property
    def response_rate(self):
        if self.times_sent == 0:
            return 0
        return round((self.response_count / self.times_sent) * 100, 1)
    
    def render_variables(self, contact, current_datetime=None):
        if current_datetime is None:
            current_datetime = timezone.now()
        
        hour = current_datetime.hour
        if hour < 12:
            saudacao = "Bom dia"
        elif hour < 18:
            saudacao = "Boa tarde"
        else:
            saudacao = "Boa noite"
        
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 
                'Sexta-feira', 'Sábado', 'Domingo']
        dia_semana = dias[current_datetime.weekday()]
        
        rendered = self.message_text
        rendered = rendered.replace('{{nome}}', contact.name or '')
        rendered = rendered.replace('{{quem_indicou}}', contact.quem_indicou or '')
        rendered = rendered.replace('{{saudacao}}', saudacao)
        rendered = rendered.replace('{{dia_semana}}', dia_semana)
        
        if hasattr(contact, 'custom_vars') and contact.custom_vars:
            for key, value in contact.custom_vars.items():
                rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        
        return rendered


class CampaignContact(models.Model):
    """Relacionamento N:N entre Campaign e Contact"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        SENT = 'sent', 'Enviada'
        DELIVERED = 'delivered', 'Entregue'
        READ = 'read', 'Lida'
        RESPONDED = 'responded', 'Respondeu'
        FAILED = 'failed', 'Falhou'
        SKIPPED = 'skipped', 'Pulado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='campaign_contacts')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.CASCADE, related_name='campaigns_participated')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    message_sent = models.ForeignKey(CampaignMessage, on_delete=models.SET_NULL, null=True, blank=True)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    evolution_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'campaigns_contact'
        indexes = [
            models.Index(fields=['campaign', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                name='unique_contact_per_campaign'
            )
        ]
    
    def __str__(self):
        return f"{self.contact.name} - {self.campaign.name}"


class CampaignLog(models.Model):
    """Log detalhado de eventos"""
    
    class Level(models.TextChoices):
        DEBUG = 'debug', 'Debug'
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Sucesso'
        WARNING = 'warning', 'Aviso'
        ERROR = 'error', 'Erro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='logs')
    contact = models.ForeignKey('contacts.Contact', on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey('authn.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO, db_index=True)
    event_type = models.CharField(max_length=50, db_index=True)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'campaigns_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', '-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.level.upper()}] {self.campaign.name} - {self.message[:50]}"


class Holiday(models.Model):
    """Feriados"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='holidays')
    
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=200)
    is_national = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'campaigns_holiday'
        ordering = ['date']
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'tenant'],
                name='unique_holiday_per_date_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.date})"
    
    @classmethod
    def is_holiday(cls, date, tenant=None):
        query = models.Q(date=date, is_active=True)
        if tenant:
            query &= (models.Q(tenant=tenant) | models.Q(is_national=True, tenant__isnull=True))
        else:
            query &= models.Q(is_national=True, tenant__isnull=True)
        return cls.objects.filter(query).exists()

