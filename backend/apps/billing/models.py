"""
Billing Models - Sistema Multi-Produto ALREA
Baseado na estratégia de produtos definida em ALREA_PRODUCTS_STRATEGY.md
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid

User = get_user_model()


class Product(models.Model):
    """
    Produtos da plataforma ALREA
    - ALREA Flow (Campanhas WhatsApp)
    - ALREA Sense (Chat)
    - ALREA API Pública (Integração Externa)
    """
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, help_text="Identificador único do produto")
    name = models.CharField(max_length=100, help_text="Nome do produto")
    description = models.TextField(help_text="Descrição detalhada do produto")
    
    # Configurações
    is_active = models.BooleanField(default=True, help_text="Produto ativo na plataforma")
    requires_ui_access = models.BooleanField(
        default=True, 
        help_text="Produto requer acesso à UI (ex: API Only = False)"
    )
    
    # Preços
    addon_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Preço como add-on (R$/mês)"
    )
    
    # Metadados
    icon = models.CharField(max_length=50, default="📦", help_text="Emoji/ícone do produto")
    color = models.CharField(max_length=7, default="#3B82F6", help_text="Cor hex do produto")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_product'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.icon} {self.name}"
    
    @property
    def is_addon_available(self):
        """Verifica se o produto pode ser vendido como add-on"""
        return self.addon_price is not None and self.addon_price > 0


class Plan(models.Model):
    """
    Planos de assinatura
    - Starter (R$ 49)
    - Pro (R$ 149) 
    - API Only (R$ 99)
    - Enterprise (R$ 499)
    """
    
    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, help_text="Identificador único do plano")
    name = models.CharField(max_length=100, help_text="Nome do plano")
    description = models.TextField(help_text="Descrição do plano")
    
    # Preços
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Preço mensal (R$)"
    )
    
    # Configurações
    is_active = models.BooleanField(default=True, help_text="Plano ativo para venda")
    
    # Metadados
    color = models.CharField(max_length=7, default="#3B82F6", help_text="Cor hex do plano")
    sort_order = models.PositiveIntegerField(default=0, help_text="Ordem de exibição")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_plan'
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'
        ordering = ['sort_order', 'price']
    
    def __str__(self):
        return f"{self.name} (R$ {self.price})"


class PlanProduct(models.Model):
    """
    Relacionamento N:N entre Planos e Produtos
    Define quais produtos estão incluídos em cada plano
    """
    
    # Relacionamentos
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='plan_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='plan_products')
    
    # Configurações
    is_included = models.BooleanField(default=True, help_text="Produto incluído no plano")
    
    # Limites (null = ilimitado)
    limit_value = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        help_text="Limite principal (ex: instâncias WhatsApp)"
    )
    limit_unit = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="Unidade do limite (ex: 'instâncias', 'análises/mês')"
    )
    # Limite secundário (ex: ALREA Chat = instâncias + usuários)
    limit_value_secondary = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Limite secundário (ex: número de usuários)"
    )
    limit_unit_secondary = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Unidade do limite secundário (ex: 'usuários')"
    )
    
    # Configurações específicas
    is_addon_available = models.BooleanField(
        default=True, 
        help_text="Permite adicionar este produto como add-on"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_plan_product'
        verbose_name = 'Produto do Plano'
        verbose_name_plural = 'Produtos dos Planos'
        unique_together = ['plan', 'product']
        ordering = ['plan__sort_order', 'product__name']
    
    def __str__(self):
        status = "Incluído" if self.is_included else "Não incluído"
        limit = f" (limite: {self.limit_value} {self.limit_unit})" if self.limit_value else " (ilimitado)"
        if self.limit_value_secondary:
            limit += f", {self.limit_value_secondary} {self.limit_unit_secondary or 'usuários'}"
        return f"{self.plan.name} → {self.product.name}: {status}{limit}"


class TenantProduct(models.Model):
    """
    Produtos ativos por tenant
    - Produtos incluídos no plano base
    - Add-ons contratados separadamente
    """
    
    # Relacionamentos
    tenant = models.ForeignKey(
        'tenancy.Tenant', 
        on_delete=models.CASCADE, 
        related_name='tenant_products',
        null=True,  # Temporariamente nulo para migração
        blank=True
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='tenant_products')
    
    # Configurações
    is_addon = models.BooleanField(default=False, help_text="Produto contratado como add-on")
    addon_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Preço pago como add-on (R$/mês)"
    )
    
    # API Key (para produtos que precisam)
    api_key = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="API Key específica do produto (se aplicável)"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Produto ativo para o tenant")
    activated_at = models.DateTimeField(default=timezone.now, help_text="Data de ativação")
    deactivated_at = models.DateTimeField(null=True, blank=True, help_text="Data de desativação")
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_tenant_product'
        verbose_name = 'Produto do Tenant'
        verbose_name_plural = 'Produtos dos Tenants'
        unique_together = ['tenant', 'product']
        ordering = ['-is_addon', 'product__name']
    
    def __str__(self):
        status = "Add-on" if self.is_addon else "Incluído"
        price = f" (R$ {self.addon_price}/mês)" if self.addon_price else ""
        return f"{self.tenant.name} → {self.product.name}: {status}{price}"
    
    def deactivate(self):
        """Desativa o produto"""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save()


class InstanceAddon(models.Model):
    """
    Add-ons de instâncias extras por produto
    - Cliente pode comprar instâncias adicionais
    - Preço por instância extra
    """
    
    # Relacionamentos
    tenant = models.ForeignKey(
        'tenancy.Tenant', 
        on_delete=models.CASCADE, 
        related_name='instance_addons',
        null=True,
        blank=True
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='instance_addons')
    
    # Configurações
    quantity = models.PositiveIntegerField(help_text="Quantidade de instâncias extras")
    price_per_instance = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Preço por instância extra (R$/mês)"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Add-on ativo")
    activated_at = models.DateTimeField(default=timezone.now, help_text="Data de ativação")
    deactivated_at = models.DateTimeField(null=True, blank=True, help_text="Data de desativação")
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_instance_addon'
        verbose_name = 'Add-on de Instância'
        verbose_name_plural = 'Add-ons de Instâncias'
        unique_together = ['tenant', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} → {self.product.name}: +{self.quantity} instâncias (R$ {self.price_per_instance}/mês)"
    
    @property
    def total_price(self):
        """Preço total do add-on"""
        return self.quantity * self.price_per_instance
    
    def deactivate(self):
        """Desativa o add-on"""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save()


class BillingHistory(models.Model):
    """
    Histórico de mudanças de billing
    - Upgrades/downgrades
    - Adição/remoção de add-ons
    - Mudanças de preço
    """
    
    # Relacionamentos
    tenant = models.ForeignKey(
        'tenancy.Tenant', 
        on_delete=models.CASCADE, 
        related_name='billing_history',
        null=True,  # Temporariamente nulo para migração
        blank=True
    )
    
    # Ação realizada
    ACTION_CHOICES = [
        ('plan_change', 'Mudança de Plano'),
        ('addon_add', 'Add-on Adicionado'),
        ('addon_remove', 'Add-on Removido'),
        ('price_change', 'Mudança de Preço'),
        ('product_activate', 'Produto Ativado'),
        ('product_deactivate', 'Produto Desativado'),
    ]
    
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True, help_text="Descrição da ação")
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        help_text="Valor da ação"
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_history'
        verbose_name = 'Histórico de Billing'
        verbose_name_plural = 'Histórico de Billing'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.get_action_display()} ({self.created_at.strftime('%d/%m/%Y')})"