from django.contrib import admin
from .models import NotificationTemplate, WhatsAppInstance, NotificationLog, SMTPConfig


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'category', 'tenant', 'is_active', 'is_global', 'created_at']
    list_filter = ['type', 'category', 'is_active', 'is_global', 'created_at']
    search_fields = ['name', 'subject', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'name', 'type', 'category', 'is_active', 'is_global')
        }),
        ('Conteúdo Email', {
            'fields': ('subject', 'content', 'html_content'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WhatsAppInstance)
class WhatsAppInstanceAdmin(admin.ModelAdmin):
    list_display = ['name', 'instance_name', 'phone_number', 'status', 'is_active', 'is_default', 'last_check']
    list_filter = ['status', 'is_active', 'is_default', 'created_at']
    search_fields = ['name', 'instance_name', 'phone_number']
    readonly_fields = ['id', 'status', 'last_check', 'last_error', 'qr_code', 'created_at', 'updated_at']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'name', 'instance_name', 'is_active', 'is_default')
        }),
        ('Configuração Evolution API', {
            'fields': ('api_url', 'api_key')
        }),
        ('Status e Conexão', {
            'fields': ('status', 'phone_number', 'qr_code', 'last_check', 'last_error'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['check_status']
    
    def check_status(self, request, queryset):
        for instance in queryset:
            instance.check_status()
        self.message_user(request, f"{queryset.count()} instâncias verificadas.")
    check_status.short_description = "Verificar status das instâncias"


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'type', 'subject', 'status', 'created_at', 'sent_at']
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['recipient__email', 'recipient__username', 'subject', 'content']
    readonly_fields = ['id', 'created_at', 'sent_at', 'delivered_at', 'read_at']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'template', 'whatsapp_instance', 'type')
        }),
        ('Destinatário', {
            'fields': ('recipient', 'recipient_email', 'recipient_phone')
        }),
        ('Conteúdo', {
            'fields': ('subject', 'content')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'external_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'delivered_at', 'read_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SMTPConfig)
class SMTPConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'port', 'from_email', 'is_active', 'is_default', 'last_test_status', 'last_test']
    list_filter = ['is_active', 'is_default', 'use_tls', 'use_ssl', 'last_test_status', 'created_at']
    search_fields = ['name', 'host', 'from_email', 'username']
    readonly_fields = ['id', 'last_test', 'last_test_status', 'last_test_error', 'created_at', 'updated_at']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'name', 'is_active', 'is_default')
        }),
        ('Configuração SMTP', {
            'fields': ('host', 'port', 'username', 'password', 'use_tls', 'use_ssl')
        }),
        ('Configuração de Email', {
            'fields': ('from_email', 'from_name')
        }),
        ('Status de Teste', {
            'fields': ('last_test', 'last_test_status', 'last_test_error'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

