from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'current_plan', 'status', 'ui_access', 'next_billing_date', 'created_at']
    list_filter = ['current_plan', 'status', 'ui_access', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'current_plan', 'status', 'ui_access')
        }),
        ('Billing', {
            'fields': ('next_billing_date',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
