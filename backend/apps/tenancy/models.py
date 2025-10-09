import uuid
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    """Tenant model for multi-tenancy with product support."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    
    # Plano atual (referência ao modelo Plan)
    current_plan = models.ForeignKey(
        'billing.Plan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tenants',
        help_text="Plano atual do tenant"
    )
    
    # Status e billing
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    next_billing_date = models.DateField(null=True, blank=True)
    
    # Configurações
    ui_access = models.BooleanField(
        default=True, 
        help_text="Tenant tem acesso à UI (ex: API Only = False)"
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenancy_tenant'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
    
    def __str__(self):
        plan_name = self.current_plan.name if self.current_plan else 'Sem Plano'
        return f"{self.name} ({plan_name})"
    
    @property
    def is_active(self):
        """Check if tenant is active."""
        return self.status == 'active'
    
    @property
    def active_products(self):
        """Lista de produtos ativos do tenant"""
        return self.tenant_products.filter(is_active=True).select_related('product')
    
    @property
    def active_product_slugs(self):
        """Lista de slugs dos produtos ativos"""
        return list(self.active_products.values_list('product__slug', flat=True))
    
    @property
    def monthly_total(self):
        """Total mensal (plano + add-ons)"""
        total = 0
        
        # Preço do plano base
        if self.current_plan:
            total += self.current_plan.price
        
        # Preços dos add-ons
        addon_total = self.tenant_products.filter(
            is_active=True, 
            is_addon=True, 
            addon_price__isnull=False
        ).aggregate(
            total=models.Sum('addon_price')
        )['total'] or 0
        
        total += addon_total
        return total
    
    def has_product(self, product_slug):
        """Verifica se o tenant tem acesso ao produto"""
        return product_slug in self.active_product_slugs
    
    def can_access_product(self, product_slug):
        """Verifica se pode acessar o produto (incluindo verificação de UI)"""
        if not self.has_product(product_slug):
            return False
        
        # Verificar se o produto requer UI e o tenant tem acesso
        try:
            from apps.billing.models import Product
            product = Product.objects.get(slug=product_slug)
            if product.requires_ui_access and not self.ui_access:
                return False
        except Product.DoesNotExist:
            return False
        
        return True
    
    def get_product_api_key(self, product_slug):
        """Obtém a API key de um produto específico"""
        try:
            tenant_product = self.tenant_products.get(
                product__slug=product_slug,
                is_active=True
            )
            return tenant_product.api_key
        except:
            return None
    
    # Métodos de compatibilidade (para não quebrar código existente)
    @property
    def plan(self):
        """Compatibilidade: retorna slug do plano"""
        return self.current_plan.slug if self.current_plan else 'starter'
    
    @property
    def plan_limits(self):
        """Compatibilidade: mantém limites antigos"""
        limits = {
            'starter': {'connections': 2, 'retention_days': 30, 'price': 49},
            'pro': {'connections': 10, 'retention_days': 180, 'price': 149},
            'api_only': {'connections': 0, 'retention_days': 0, 'price': 99},
            'enterprise': {'connections': -1, 'retention_days': 730, 'price': 499},
        }
        return limits.get(self.plan, limits['starter'])
    
    def can_add_connection(self, current_count):
        """Compatibilidade: verifica se pode adicionar conexão"""
        limit = self.plan_limits['connections']
        return limit == -1 or current_count < limit
