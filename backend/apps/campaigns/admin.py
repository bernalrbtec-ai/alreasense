from django.contrib import admin
from apps.campaigns.models import (
    Campaign, CampaignMessage, CampaignContact, CampaignLog, Holiday
)


class CampaignMessageInline(admin.TabularInline):
    model = CampaignMessage
    extra = 1
    fields = ['order', 'message_text', 'is_active', 'times_sent', 'response_count']
    readonly_fields = ['times_sent', 'response_count']


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'status', 'instance', 'progress_percentage', 'created_at']
    list_filter = ['status', 'is_paused', 'schedule_type', 'tenant', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'id', 'progress_percentage', 'response_rate', 'can_be_started',
        'created_at', 'updated_at', 'started_at', 'paused_at', 'completed_at', 'cancelled_at'
    ]
    inlines = [CampaignMessageInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('tenant', 'name', 'description', 'instance', 'status', 'is_paused')
        }),
        ('Agendamento', {
            'fields': (
                'schedule_type', 'morning_start', 'morning_end',
                'afternoon_start', 'afternoon_end', 'skip_weekends', 'skip_holidays'
            )
        }),
        ('Métricas', {
            'fields': (
                'total_contacts', 'sent_messages', 'failed_messages', 'responded_count',
                'progress_percentage', 'response_rate'
            )
        }),
        ('Controle', {
            'fields': ('next_scheduled_send', 'last_send_at', 'last_heartbeat', 'is_processing')
        }),
        ('Auditoria', {
            'fields': (
                'created_by', 'started_by', 'created_at', 'updated_at',
                'started_at', 'paused_at', 'completed_at', 'cancelled_at'
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'order', 'message_preview', 'is_active', 'times_sent', 'response_rate']
    list_filter = ['is_active', 'campaign__tenant']
    search_fields = ['message_text', 'campaign__name']
    
    def message_preview(self, obj):
        return obj.message_text[:100]
    message_preview.short_description = 'Mensagem'


@admin.register(CampaignContact)
class CampaignContactAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'contact', 'status', 'sent_at', 'responded_at']
    list_filter = ['status', 'campaign__tenant']
    search_fields = ['contact__name', 'contact__phone', 'campaign__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CampaignLog)
class CampaignLogAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'level', 'event_type', 'message_preview', 'created_at']
    list_filter = ['level', 'event_type', 'campaign__tenant', 'created_at']
    search_fields = ['message', 'campaign__name']
    readonly_fields = ['id', 'created_at']
    
    def message_preview(self, obj):
        return obj.message[:100]
    message_preview.short_description = 'Mensagem'


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'is_national', 'tenant', 'is_active']
    list_filter = ['is_national', 'is_active', 'date', 'tenant']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at']

