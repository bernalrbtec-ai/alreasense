"""
BillingConfig - Configurações do sistema de cobrança por tenant
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class BillingConfig(models.Model):
    """
    Configurações do sistema de cobrança para um tenant
    
    OneToOne com Tenant - cada tenant tem uma única configuração
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_config',
        verbose_name='Tenant'
    )
    
    # Throttling (mensagens por minuto)
    messages_per_minute = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text='Máximo de mensagens por minuto (1-60)'
    )
    
    # Limites
    max_messages_per_day = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text='Máximo de mensagens por dia (0 = ilimitado)',
        null=True,
        blank=True
    )
    
    # Rate limiting da API
    api_rate_limit_per_hour = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0)],
        help_text='Máximo de requisições API por hora (0 = ilimitado)',
        null=True,
        blank=True
    )
    
    # API habilitada
    api_enabled = models.BooleanField(
        default=True,
        help_text='API de Billing habilitada para este tenant'
    )
    
    # Configurações de retry
    max_retry_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text='Máximo de tentativas de retry'
    )
    
    retry_delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Delay entre tentativas (em minutos)'
    )
    
    # Batch size
    max_batch_size = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text='Máximo de contatos por campanha'
    )
    
    # Notificações
    notify_on_instance_down = models.BooleanField(
        default=False,
        help_text='Notificar quando instância cair'
    )
    
    notify_on_resume = models.BooleanField(
        default=False,
        help_text='Notificar quando instância voltar'
    )
    
    # Comportamento
    close_conversation_after_send = models.BooleanField(
        default=True,
        help_text='Fechar conversa automaticamente após envio'
    )
    
    # Horário comercial (usa BusinessHours do chat)
    use_business_hours = models.BooleanField(
        default=True,
        help_text='Respeitar horário comercial para envios'
    )
    
    # Configurações de retry
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text='Máximo de tentativas em caso de falha'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_config'
        verbose_name = 'Configuração de Billing'
        verbose_name_plural = 'Configurações de Billing'
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        return f"BillingConfig - {self.tenant.name}"



