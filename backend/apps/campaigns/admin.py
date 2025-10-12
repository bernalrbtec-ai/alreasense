from django.contrib import admin
from .models import Campaign, CampaignMessage, CampaignContact, CampaignLog


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'status', 'rotation_mode', 'total_contacts', 'messages_sent', 'success_rate', 'created_at']
    list_filter = ['status', 'rotation_mode', 'created_at']
    search_fields = ['name', 'tenant__name']
    readonly_fields = ['id', 'total_contacts', 'messages_sent', 'messages_delivered', 'messages_read', 'messages_failed', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'name', 'description', 'created_by')
        }),
        ('Configurações', {
            'fields': ('rotation_mode', 'instances', 'contact_list', 'interval_min', 'interval_max', 'daily_limit_per_instance', 'pause_on_health_below')
        }),
        ('Agendamento', {
            'fields': ('scheduled_at', 'started_at', 'completed_at')
        }),
        ('Status e Métricas', {
            'fields': ('status', 'total_contacts', 'messages_sent', 'messages_delivered', 'messages_read', 'messages_failed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'order', 'times_used', 'created_at']
    list_filter = ['campaign', 'created_at']
    search_fields = ['campaign__name', 'content']


@admin.register(CampaignContact)
class CampaignContactAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'contact', 'status', 'instance_used', 'sent_at', 'delivered_at', 'retry_count']
    list_filter = ['status', 'sent_at']
    search_fields = ['campaign__name', 'contact__name', 'contact__phone']
    readonly_fields = ['id', 'whatsapp_message_id', 'sent_at', 'delivered_at', 'read_at', 'failed_at', 'created_at', 'updated_at']


@admin.register(CampaignLog)
class CampaignLogAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'log_type', 'severity', 'message', 'instance', 'contact', 'created_at']
    list_filter = ['log_type', 'severity', 'created_at']
    search_fields = ['campaign__name', 'message']
    readonly_fields = ['id', 'campaign', 'log_type', 'severity', 'message', 'details', 'instance', 'contact', 'campaign_contact', 'duration_ms', 'request_data', 'response_data', 'http_status', 'campaign_progress', 'instance_health_score', 'created_by', 'created_at']
    
    def has_add_permission(self, request):
        # Logs são criados automaticamente, não manualmente
        return False
    
    def has_change_permission(self, request, obj=None):
        # Logs não devem ser editados
        return False
