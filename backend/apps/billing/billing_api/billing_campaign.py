"""
BillingCampaign - Campanha de cobrança (reutiliza Campaign)
"""
from django.db import models
import uuid


class BillingCampaign(models.Model):
    """
    Campanha de cobrança
    
    OneToOne com Campaign - reutiliza toda a infraestrutura de campanhas
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_campaigns',
        verbose_name='Tenant'
    )
    
    # Relacionamento com Campaign (reutiliza)
    campaign = models.OneToOneField(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name='billing_campaign',
        verbose_name='Campanha'
    )
    
    # Template usado
    template = models.ForeignKey(
        'billing.BillingTemplate',
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='Template'
    )
    
    # ID externo (fornecido pelo cliente)
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='ID externo fornecido pelo cliente (opcional)'
    )
    
    # Tipo de cobrança
    billing_type = models.CharField(
        max_length=20,
        choices=[
            ('overdue', 'Cobrança Atrasada'),
            ('upcoming', 'Cobrança a Vencer'),
            ('notification', 'Notificação'),
        ],
        help_text='Tipo de cobrança'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_campaign'
        verbose_name = 'Campanha de Billing'
        verbose_name_plural = 'Campanhas de Billing'
        indexes = [
            models.Index(fields=['tenant', 'billing_type']),
            models.Index(fields=['external_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"BillingCampaign - {self.campaign.name} ({self.get_billing_type_display()})"



