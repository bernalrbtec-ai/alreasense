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
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento com BillingCampaign
    billing_campaign = models.ForeignKey(
        'billing_api.BillingCampaign',
        on_delete=models.CASCADE,
        related_name='billing_contacts',
        verbose_name='Campanha de Billing'
    )
    
    # Relacionamento com CampaignContact (reutiliza)
    campaign_contact = models.OneToOneField(
        'campaigns.CampaignContact',
        on_delete=models.CASCADE,
        related_name='billing_contact',
        verbose_name='Contato da Campanha'
    )
    
    # Variação de template usada
    template_variation = models.ForeignKey(
        'billing_api.BillingTemplateVariation',
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
        db_table = 'billing_api_contact'
        verbose_name = 'Contato de Billing'
        verbose_name_plural = 'Contatos de Billing'
        indexes = [
            models.Index(fields=['billing_campaign', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        contact_name = self.campaign_contact.contact.name if self.campaign_contact.contact else 'N/A'
        return f"BillingContact - {contact_name} ({self.get_status_display()})"



