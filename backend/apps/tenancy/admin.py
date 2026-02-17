from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Tenant, TenantCompanyProfile

User = get_user_model()


@admin.register(TenantCompanyProfile)
class TenantCompanyProfileAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'razao_social', 'cnpj', 'updated_at']
    search_fields = ['razao_social', 'cnpj']
    raw_id_fields = ['tenant']
    readonly_fields = ['id', 'created_at', 'updated_at']


class TenantUserInline(admin.TabularInline):
    """Inline para mostrar usuários do tenant"""
    model = User
    extra = 0
    fields = ['email', 'first_name', 'last_name', 'role', 'is_active']
    readonly_fields = ['email']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class TenantDepartmentInline(admin.TabularInline):
    """Inline para mostrar departamentos do tenant"""
    from apps.authn.models import Department
    model = Department
    extra = 0
    fields = ['name', 'color', 'ai_enabled']
    can_delete = True


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'current_plan', 'status', 'ui_access', 'products_display', 'created_at']
    list_filter = ['current_plan', 'status', 'ui_access', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'products_display', 'monthly_total_display']
    inlines = [TenantDepartmentInline, TenantUserInline]
    
    fieldsets = (
        ('📋 Informações Básicas', {
            'fields': ('id', 'name')
        }),
        ('💳 Plano e Produtos', {
            'fields': ('current_plan', 'ui_access', 'products_display', 'monthly_total_display'),
            'description': 'Configure o plano base. Produtos adicionais (add-ons) são gerenciados em "Produtos dos Tenants".'
        }),
        ('📊 Status e Billing', {
            'fields': ('status', 'next_billing_date')
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def products_display(self, obj):
        """Mostra produtos ativos"""
        if not obj.current_plan:
            return "Sem produtos"
        
        products = obj.active_product_slugs
        if not products:
            return "Nenhum produto ativo"
        
        product_names = {
            'flow': '📤 Flow',
            'sense': '🧠 Sense',
            'api_public': '🔌 API Pública'
        }
        
        badges = [product_names.get(p, p) for p in products]
        return " | ".join(badges)
    products_display.short_description = 'Produtos Ativos'
    
    def monthly_total_display(self, obj):
        """Mostra valor total mensal"""
        try:
            total = obj.monthly_total
            return f"R$ {total:.2f}/mês"
        except:
            return "N/A"
    monthly_total_display.short_description = 'Valor Mensal'
    
    def save_model(self, request, obj, form, change):
        """Ao salvar tenant, criar usuário admin se for novo"""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        if is_new:
            # Será criado manualmente pelo admin via "Criar Usuário" action
            pass
    
    actions = ['create_user_for_tenant']
    
    def create_user_for_tenant(self, request, queryset):
        """Action para criar usuário para tenant selecionado"""
        if queryset.count() != 1:
            self.message_user(request, "Selecione apenas 1 tenant por vez", level='warning')
            return
        
        tenant = queryset.first()
        
        # Redirecionar para página de criação de usuário
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Por enquanto, mostrar mensagem
        self.message_user(
            request, 
            f"Para criar usuário para '{tenant.name}', use: Admin → Usuários → Adicionar usuário → Selecione o tenant '{tenant.name}'",
            level='info'
        )
    
    create_user_for_tenant.short_description = "➕ Criar usuário para tenant selecionado"
