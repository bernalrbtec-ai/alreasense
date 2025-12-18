"""
BillingTemplate e BillingTemplateVariation - Templates de mensagens de cobrança
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class BillingTemplate(models.Model):
    """
    Template de mensagem de cobrança
    
    Cada tenant pode ter templates para os 3 tipos:
    - overdue (cobrança atrasada)
    - upcoming (cobrança a vencer)
    - notification (avisos)
    """
    
    TEMPLATE_TYPE_CHOICES = [
        ('overdue', 'Cobrança Atrasada'),
        ('upcoming', 'Cobrança a Vencer'),
        ('notification', 'Notificação/Aviso'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_templates',
        verbose_name='Tenant'
    )
    
    # Identificação
    name = models.CharField(
        max_length=100,
        help_text='Nome do template (ex: "Cobrança Atrasada - Padrão")'
    )
    
    # Tipo de template
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        help_text='Tipo de template'
    )
    
    # Descrição
    description = models.TextField(
        blank=True,
        help_text='Descrição do template'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Template ativo'
    )
    
    # Estatísticas
    total_uses = models.IntegerField(
        default=0,
        help_text='Total de vezes que este template foi usado'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_template'
        verbose_name = 'Template de Billing'
        verbose_name_plural = 'Templates de Billing'
        unique_together = ['tenant', 'name', 'template_type']
        indexes = [
            models.Index(fields=['tenant', 'template_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()}) - {self.tenant.name}"


class BillingTemplateVariation(models.Model):
    """
    Variação de template (anti-bloqueio WhatsApp)
    
    Cada template pode ter até 5 variações para reduzir
    a chance de bloqueio do WhatsApp
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        BillingTemplate,
        on_delete=models.CASCADE,
        related_name='variations',
        verbose_name='Template'
    )
    
    # Nome da variação
    name = models.CharField(
        max_length=100,
        help_text='Nome da variação (ex: "Variação 1")'
    )
    
    # Ordem (1-5)
    order = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Ordem da variação (1-5)'
    )
    
    # Template com variáveis
    # Variáveis disponíveis:
    # - {{nome_cliente}}
    # - {{valor}}
    # - {{data_vencimento}}
    # - {{dias_atraso}} (para overdue)
    # - {{dias_vencimento}} (para upcoming)
    # - {{link_pagamento}} (opcional - só aparece se fornecido)
    # - {{codigo_pix}} (opcional - só aparece se fornecido)
    # - {{observacoes}} (opcional)
    template_text = models.TextField(
        help_text='Texto do template com variáveis (ex: Olá {{nome_cliente}}, sua cobrança de R$ {{valor}} vence em {{dias_vencimento}} dias)'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Variação ativa'
    )
    
    # Estatísticas
    times_used = models.IntegerField(
        default=0,
        help_text='Quantas vezes esta variação foi usada'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_template_variation'
        verbose_name = 'Variação de Template'
        verbose_name_plural = 'Variações de Template'
        unique_together = ['template', 'order']
        indexes = [
            models.Index(fields=['template', 'is_active', 'order']),
        ]
    
    def __str__(self):
        return f"Variação {self.order} - {self.template.name}"



