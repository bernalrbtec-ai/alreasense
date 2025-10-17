from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin para Departamentos."""
    list_display = ['name', 'tenant', 'color', 'ai_enabled', 'created_at']
    list_filter = ['tenant', 'ai_enabled', 'created_at']
    search_fields = ['name', 'tenant__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'name', 'color')
        }),
        ('Configurações', {
            'fields': ('ai_enabled',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'tenant', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'tenant', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    filter_horizontal = ['departments']  # Para ManyToMany
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Tenant & Role', {
            'fields': ('tenant', 'role', 'departments')
        }),
        ('Informações Adicionais', {
            'fields': ('display_name', 'phone', 'birth_date', 'avatar'),
            'classes': ('collapse',)
        }),
        ('Notificações', {
            'fields': ('notify_email', 'notify_whatsapp'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Tenant & Role', {
            'fields': ('tenant', 'role')
        }),
    )
