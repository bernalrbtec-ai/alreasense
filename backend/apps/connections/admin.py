from django.contrib import admin
from .models import EvolutionConnection


@admin.register(EvolutionConnection)
class EvolutionConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'tenant']
    search_fields = ['name', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'is_active')
        }),
        ('Evolution API', {
            'fields': ('evo_ws_url', 'evo_token')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
