from django.contrib import admin
from .models import Campaign, CampaignMessage, CampaignContact, CampaignLog
# CampaignNotification temporariamente comentado


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


# Temporariamente comentado
# @admin.register(CampaignNotification)
# class CampaignNotificationAdmin(admin.ModelAdmin):
#     list_display = ['contact_name', 'campaign_name', 'notification_type', 'status', 'received_timestamp', 'created_at']
#     list_filter = ['notification_type', 'status', 'created_at', 'received_timestamp']
#     search_fields = ['contact__name', 'contact__phone', 'campaign__name', 'received_message']
#     readonly_fields = ['id', 'received_timestamp', 'created_at', 'updated_at']
#     
#     fieldsets = (
#         ('Informações Básicas', {
#             'fields': ('id', 'tenant', 'campaign', 'contact', 'campaign_contact', 'instance')
#         }),
#         ('Notificação', {
#             'fields': ('notification_type', 'status', 'received_message', 'received_timestamp')
#         }),
#         ('Resposta', {
#             'fields': ('sent_reply', 'sent_timestamp', 'sent_by')
#         }),
#         ('Metadados', {
#             'fields': ('whatsapp_message_id', 'details')
#         }),
#         ('Timestamps', {
#             'fields': ('created_at', 'updated_at')
#         }),
#     )
#     
#     def contact_name(self, obj):
#         return obj.contact.name if obj.contact else 'N/A'
#     contact_name.short_description = 'Contato'
#     
#     def campaign_name(self, obj):
#         return obj.campaign.name if obj.campaign else 'N/A'
#     campaign_name.short_description = 'Campanha'
