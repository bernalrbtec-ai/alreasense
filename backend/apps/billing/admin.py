"""
Admin para o app billing
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Plan, PlanProduct, TenantProduct, BillingHistory


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['icon_display', 'name', 'slug', 'addon_price_display', 'is_active', 'requires_ui_access', 'tenant_count']
    list_filter = ['is_active', 'requires_ui_access']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'tenant_count']
    ordering = ['name']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('id', 'slug', 'name', 'description')
        }),
        ('Configurações', {
            'fields': ('icon', 'color', 'is_active', 'requires_ui_access')
        }),
        ('Preços', {
            'fields': ('addon_price',)
        }),
        ('Estatísticas', {
            'fields': ('tenant_count',),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def icon_display(self, obj):
        if obj.icon:
            return format_html('<span style="font-size: 18px;">{}</span>', obj.icon)
        return '-'
    icon_display.short_description = 'Ícone'
    
    def addon_price_display(self, obj):
        if obj.addon_price:
            return format_html('<span style="color: green; font-weight: bold;">R$ {:.2f}</span>', obj.addon_price)
        return format_html('<span style="color: gray;">Não disponível</span>')
    addon_price_display.short_description = 'Preço Add-on'
    
    def tenant_count(self, obj):
        count = obj.tenant_products.filter(is_active=True).count()
        return format_html('<span style="color: blue; font-weight: bold;">{} clientes</span>', count)
    tenant_count.short_description = 'Clientes Ativos'


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price_display', 'is_active', 'sort_order', 'tenant_count', 'total_mrr']
    list_filter = ['is_active']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'tenant_count', 'total_mrr']
    ordering = ['sort_order', 'price']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('id', 'slug', 'name', 'description')
        }),
        ('Preços e Configurações', {
            'fields': ('price', 'is_active', 'sort_order')
        }),
        ('Aparência', {
            'fields': ('color',)
        }),
        ('Estatísticas', {
            'fields': ('tenant_count', 'total_mrr'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def price_display(self, obj):
        return format_html('<span style="color: green; font-weight: bold;">R$ {:.2f}</span>', obj.price)
    price_display.short_description = 'Preço'
    
    def tenant_count(self, obj):
        count = obj.tenants.filter(is_active=True).count()
        return format_html('<span style="color: blue; font-weight: bold;">{} clientes</span>', count)
    tenant_count.short_description = 'Clientes'
    
    def total_mrr(self, obj):
        count = obj.tenants.filter(is_active=True).count()
        total = count * obj.price
        return format_html('<span style="color: green; font-weight: bold;">R$ {:.2f}</span>', total)
    total_mrr.short_description = 'MRR Total'


class PlanProductInline(admin.TabularInline):
    model = PlanProduct
    extra = 0
    fields = ['product', 'is_included', 'limit_value', 'limit_unit', 'is_addon_available']
    readonly_fields = []


@admin.register(PlanProduct)
class PlanProductAdmin(admin.ModelAdmin):
    list_display = ['plan', 'product', 'is_included', 'limit_display', 'is_addon_available']
    list_filter = ['is_included', 'is_addon_available', 'plan', 'product']
    search_fields = ['plan__name', 'product__name']
    readonly_fields = ['created_at']
    
    def limit_display(self, obj):
        if obj.limit_value:
            return f"{obj.limit_value} {obj.limit_unit or ''}"
        return "Ilimitado"
    limit_display.short_description = 'Limite'


@admin.register(TenantProduct)
class TenantProductAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'product', 'is_addon', 'addon_price', 'is_active', 'activated_at']
    list_filter = ['is_addon', 'is_active', 'product', 'activated_at']
    search_fields = ['tenant__name', 'product__name']
    readonly_fields = ['id', 'activated_at', 'deactivated_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Relacionamentos', {
            'fields': ('id', 'tenant', 'product')
        }),
        ('Configurações', {
            'fields': ('is_addon', 'addon_price', 'api_key', 'is_active')
        }),
        ('Datas', {
            'fields': ('activated_at', 'deactivated_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'action', 'description', 'amount', 'created_at']
    list_filter = ['action', 'created_at', 'tenant']
    search_fields = ['tenant__name', 'description']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Ação', {
            'fields': ('id', 'tenant', 'action', 'description')
        }),
        ('Valores', {
            'fields': ('amount',)
        }),
        ('Metadados', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# Adicionar inline no PlanAdmin
PlanAdmin.inlines = [PlanProductInline]