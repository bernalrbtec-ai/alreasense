"""
BillingQueue - Fila de processamento de cobranças
"""
from django.db import models
from django.utils import timezone
import uuid


class BillingQueue(models.Model):
    """
    Fila de processamento de cobranças
    
    Controla o processamento de uma campanha de billing,
    incluindo pausa/retomada, progresso, etc.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('running', 'Em Execução'),
        ('paused', 'Pausada'),
        ('paused_business_hours', 'Pausada - Fora do Horário Comercial'),
        ('paused_instance_down', 'Pausada - Instância Offline'),
        ('completed', 'Concluída'),
        ('cancelled', 'Cancelada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento com BillingCampaign (OneToOne)
    billing_campaign = models.OneToOneField(
        'billing.BillingCampaign',
        on_delete=models.CASCADE,
        related_name='queue',
        verbose_name='Campanha de Billing'
    )
    
    # Status
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Status da fila'
    )
    
    # Progresso
    total_contacts = models.IntegerField(
        default=0,
        help_text='Total de contatos na campanha'
    )
    processed_contacts = models.IntegerField(
        default=0,
        help_text='Contatos processados'
    )
    sent_contacts = models.IntegerField(
        default=0,
        help_text='Contatos com mensagem enviada'
    )
    failed_contacts = models.IntegerField(
        default=0,
        help_text='Contatos com falha'
    )
    
    # Worker que está processando (se houver)
    processing_by = models.CharField(
        max_length=255,
        blank=True,
        help_text='ID do worker que está processando (se houver)'
    )
    
    # Heartbeat (última atualização do worker)
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Último heartbeat do worker'
    )
    
    # Próxima execução (para retomadas)
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Próxima execução agendada (para retomadas)'
    )
    
    # Timestamps
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando a fila começou a ser processada'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando a fila foi concluída'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_queue'
        verbose_name = 'Fila de Billing'
        verbose_name_plural = 'Filas de Billing'
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['processing_by', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"BillingQueue - {self.billing_campaign.campaign.name} ({self.get_status_display()})"
    
    @property
    def progress_percentage(self):
        """Calcula porcentagem de progresso"""
        if self.total_contacts == 0:
            return 0
        return int((self.processed_contacts / self.total_contacts) * 100)
    
    @property
    def estimated_time_remaining(self):
        """Calcula tempo estimado restante (em minutos)"""
        if self.processed_contacts == 0 or self.total_contacts == 0:
            return None
        
        # Taxa de processamento (contatos por minuto)
        if self.started_at:
            elapsed_minutes = (timezone.now() - self.started_at).total_seconds() / 60
            if elapsed_minutes > 0:
                rate = self.processed_contacts / elapsed_minutes
                remaining = self.total_contacts - self.processed_contacts
                if rate > 0:
                    return int(remaining / rate)
        return None



