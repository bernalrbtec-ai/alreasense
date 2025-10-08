from django.contrib import admin
from .models import EvolutionConnection


@admin.register(EvolutionConnection)
class EvolutionConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_url', 'status', 'is_active', 'created_at']
    list_filter = ['is_active', 'status', 'created_at']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at', 'last_check']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'status')
        }),
        ('Evolution API Configuration', {
            'fields': ('base_url', 'api_key', 'webhook_url')
        }),
        ('Status Information', {
            'fields': ('last_check', 'last_error'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
