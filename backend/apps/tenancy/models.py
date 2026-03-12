import uuid
from django.db import models
from django.utils import timezone


class TenantCompanyProfile(models.Model):
    """
    Perfil da empresa por tenant (dados para cobrança, faturamento e BIA).
    Tabela criada via SQL direto – ver docs/sql/tenancy_company_profile.sql
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='company_profile',
        db_column='tenant_id',
    )
    razao_social = models.CharField(max_length=200, blank=True, null=True)
    cnpj = models.CharField(max_length=18, blank=True, null=True)  # legado; preferir documento+tipo_pessoa
    tipo_pessoa = models.CharField(max_length=2, blank=True, default='PJ')  # PF ou PJ
    documento = models.CharField(max_length=18, blank=True, null=True)  # CPF ou CNPJ (só dígitos)
    nome_fantasia = models.CharField(max_length=200, blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    endereco_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    endereco_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email_principal = models.EmailField(max_length=254, blank=True, null=True)
    ramo_atuacao = models.CharField(max_length=100, blank=True, null=True)
    data_fundacao = models.DateField(blank=True, null=True)
    missao = models.TextField(blank=True, null=True)
    sobre_empresa = models.TextField(blank=True, null=True)
    produtos_servicos = models.TextField(blank=True, null=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenancy_company_profile'
        managed = False  # Tabela criada via SQL direto
        verbose_name = 'Perfil da Empresa'
        verbose_name_plural = 'Perfis de Empresas'

    def __str__(self):
        return f"{self.razao_social or 'Sem nome'} ({self.tenant.name})"


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
    allow_meta_interactive_buttons = models.BooleanField(
        default=True,
        help_text="Permite envio de mensagens com reply buttons (Meta, janela 24h). Desative para desabilitar a feature por tenant.",
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
        """Verifica se pode acessar o produto (incluindo verificação de UI).
        ALREA Chat unifica: chat, respostas rápidas, agenda e contatos — ter produto 'chat' concede acesso a 'contacts' e 'agenda'."""
        has_access = self.has_product(product_slug) or (
            product_slug in ('contacts', 'agenda') and self.has_product('chat')
        )
        if not has_access:
            return False
        effective_slug = 'chat' if product_slug in ('contacts', 'agenda') and self.has_product('chat') and not self.has_product(product_slug) else product_slug
        try:
            from apps.billing.models import Product
            product = Product.objects.get(slug=effective_slug)
            if product.requires_ui_access and not self.ui_access:
                return False
        except Product.DoesNotExist:
            return False
        return True
    
    def get_product_limit(self, product_slug, limit_type='instances'):
        """Obtém o limite de um produto específico para o tenant.
        limit_type: 'instances', 'campaigns', 'analyses', 'users' (users usa limit_value_secondary do PlanProduct)."""
        if not self.current_plan:
            return None
        from apps.billing.models import PlanProduct
        try:
            plan_product = PlanProduct.objects.get(
                plan=self.current_plan,
                product__slug=product_slug,
                is_included=True
            )
            if limit_type == 'users':
                return getattr(plan_product, 'limit_value_secondary', None)
            if limit_type in ('instances', 'campaigns', 'analyses'):
                return plan_product.limit_value
            return plan_product.limit_value
        except PlanProduct.DoesNotExist:
            return None
    
    def get_current_usage(self, product_slug, usage_type='instances'):
        """Obtém o uso atual de um produto específico.
        usage_type: 'instances', 'campaigns', 'analyses', 'users'."""
        if usage_type == 'instances':
            from apps.notifications.models import WhatsAppInstance
            return WhatsAppInstance.objects.filter(tenant=self).count()
        elif usage_type == 'campaigns':
            from apps.campaigns.models import Campaign
            return Campaign.objects.filter(tenant=self).count()
        elif usage_type == 'analyses':
            from apps.chat_messages.models import ChatMessage
            return ChatMessage.objects.filter(tenant=self).count()
        elif usage_type == 'users':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.filter(tenant=self).count()
        return 0
    
    def has_chat_for_instances(self):
        """Verifica se o tenant tem acesso a Chat para criação de instâncias.
        True se tem TenantProduct chat ativo OU se o plano atual inclui Chat (fallback quando tenant_products está desatualizado)."""
        if self.has_product('chat'):
            return True
        if not self.current_plan:
            return False
        from apps.billing.models import PlanProduct
        return PlanProduct.objects.filter(
            plan=self.current_plan,
            product__slug='chat',
            is_included=True
        ).exists()
    
    def can_create_instance(self):
        """Verifica se pode criar nova instância WhatsApp.
        Chat é o produto 'pai': os limites (instâncias e usuários) vêm sempre do Chat. Flow é add-on (apenas campanhas)."""
        if not self.has_chat_for_instances():
            return False, 'Produto ALREA Chat não disponível no seu plano (instâncias WhatsApp)'
        product_slug = 'chat'
        limit = self.get_product_limit(product_slug, 'instances')
        if limit is None:  # Ilimitado
            return True, None
        current = self.get_current_usage(product_slug, 'instances')
        if current >= limit:
            return False, f'Limite de {limit} instâncias atingido. Upgrade seu plano para mais instâncias.'
        return True, None

    def get_instance_limit_info(self):
        """Retorna informações sobre limite de instâncias.
        Os limites vêm do produto Chat (pai); Flow não define limite de instâncias."""
        if not self.has_chat_for_instances():
            return {
                'has_access': False,
                'current': 0,
                'limit': 0,
                'unlimited': False,
                'message': 'Produto ALREA Chat não disponível no seu plano (instâncias WhatsApp)'
            }
        product_slug = 'chat'
        limit = self.get_product_limit(product_slug, 'instances')
        current = self.get_current_usage(product_slug, 'instances')
        return {
            'has_access': True,
            'current': current,
            'limit': limit,
            'unlimited': limit is None,
            'can_create': current < (limit or float('inf')),
            'message': None if limit is None else f'{current}/{limit} instâncias'
        }
    
    def get_product_api_key(self, product_slug):
        """Obtém a API key de um produto específico"""
        try:
            tenant_product = self.tenant_products.get(
                product__slug=product_slug,
                is_active=True
            )
            return tenant_product.api_key
        except Exception:
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
