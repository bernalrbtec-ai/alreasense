"""
BillingContact - Contato de cobrança (reutiliza CampaignContact)
"""
from django.db import models
import uuid


class BillingContact(models.Model):
    """
    Contato de cobrança
    
    OneToOne com CampaignContact - reutiliza toda a infraestrutura
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sending', 'Enviando'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregue'),
        ('read', 'Lida'),
        ('failed', 'Falhou'),
        ('pending_retry', 'Pendente Retry'),
        ('cancelled', 'Cancelado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento com BillingCampaign (nullable para mensagens agendadas)
    billing_campaign = models.ForeignKey(
        'billing.BillingCampaign',
        on_delete=models.CASCADE,
        related_name='billing_contacts',
        verbose_name='Campanha de Billing',
        null=True,
        blank=True
    )
    
    # Relacionamento com BillingCycle (para mensagens agendadas)
    billing_cycle = models.ForeignKey(
        'billing.BillingCycle',
        on_delete=models.CASCADE,
        related_name='billing_contacts',
        verbose_name='Ciclo de Billing',
        null=True,
        blank=True
    )
    
    # Relacionamento com CampaignContact (reutiliza)
    # IMPORTANTE: Nullable porque mensagens agendadas não têm CampaignContact até serem enviadas
    campaign_contact = models.OneToOneField(
        'campaigns.CampaignContact',
        on_delete=models.CASCADE,
        related_name='billing_contact',
        verbose_name='Contato da Campanha',
        null=True,
        blank=True
    )
    
    # Variação de template usada
    template_variation = models.ForeignKey(
        'billing.BillingTemplateVariation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billing_contacts',
        verbose_name='Variação de Template'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Status do envio'
    )
    
    # Mensagem renderizada (com variáveis substituídas)
    rendered_message = models.TextField(
        blank=True,
        help_text='Mensagem final renderizada (com variáveis substituídas)'
    )
    
    # Dados da cobrança (JSON)
    billing_data = models.JSONField(
        default=dict,
        help_text='Dados da cobrança (valor, vencimento, link, pix, etc.)'
    )
    
    # Campos de ciclo (para mensagens agendadas)
    cycle_message_type = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text='Tipo de mensagem do ciclo (upcoming_5d, overdue_1d, etc)'
    )
    cycle_index = models.IntegerField(
        null=True,
        blank=True,
        help_text='Índice da mensagem no ciclo (1-6)'
    )
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Data agendada para envio (já recalculada para dia útil)'
    )
    billing_status = models.CharField(
        max_length=20,
        default='active',
        help_text='Status da cobrança (active, cancelled, paid)'
    )
    
    # Retry
    retry_count = models.IntegerField(
        default=0,
        help_text='Contador de tentativas'
    )
    last_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última tentativa de retry'
    )
    
    # Version para lock otimista
    version = models.IntegerField(
        default=0,
        help_text='Versão do registro (para lock otimista)'
    )
    
    # Timestamps
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando a mensagem deve ser enviada'
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Quando a mensagem foi enviada'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_contact'
        verbose_name = 'Contato de Billing'
        verbose_name_plural = 'Contatos de Billing'
        indexes = [
            models.Index(fields=['billing_campaign', 'status']),
            models.Index(fields=['billing_cycle', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['billing_status', 'scheduled_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        if self.campaign_contact and self.campaign_contact.contact:
            contact_name = self.campaign_contact.contact.name
        elif self.billing_cycle:
            contact_name = self.billing_cycle.contact_name
        else:
            contact_name = 'N/A'
        return f"BillingContact - {contact_name} ({self.get_status_display()})"



