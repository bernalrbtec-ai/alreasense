from django.contrib import admin
from .models import EvolutionConnection


@admin.register(EvolutionConnection)
class EvolutionConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'base_url', 'status', 'is_active', 'created_at']
    list_filter = ['is_active', 'status', 'created_at', 'tenant']
    search_fields = ['name', 'base_url', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at', 'last_check']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'is_active', 'status')
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
    
    def get_queryset(self, request):
        """Superuser vê todas as conexões, outros usuários veem apenas do seu tenant."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        else:
            return qs.filter(tenant=request.user.tenant)
