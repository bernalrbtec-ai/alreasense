"""
Admin para Flow Chat.
"""
from django.contrib import admin
from apps.chat.models import Conversation, Message, MessageAttachment
from apps.chat.models_business_hours import BusinessHours, AfterHoursMessage, AfterHoursTaskConfig


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin para Conversas."""
    
    list_display = [
        'contact_phone', 'contact_name', 'tenant', 'department',
        'assigned_to', 'status', 'last_message_at', 'created_at'
    ]
    list_filter = ['status', 'tenant', 'department', 'created_at']
    search_fields = ['contact_phone', 'contact_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_message_at']
    filter_horizontal = ['participants']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'department', 'contact_phone', 'contact_name')
        }),
        ('Gerenciamento', {
            'fields': ('assigned_to', 'status', 'participants')
        }),
        ('Metadados', {
            'fields': ('metadata', 'last_message_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class MessageAttachmentInline(admin.TabularInline):
    """Inline para anexos de mensagem."""
    model = MessageAttachment
    extra = 0
    readonly_fields = ['id', 'original_filename', 'mime_type', 'storage_type', 'size_bytes', 'created_at']
    fields = ['original_filename', 'mime_type', 'storage_type', 'size_bytes', 'file_url']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin para Mensagens."""
    
    list_display = [
        'get_contact', 'direction', 'status', 'sender',
        'is_internal', 'created_at'
    ]
    list_filter = ['direction', 'status', 'is_internal', 'created_at']
    search_fields = ['conversation__contact_phone', 'conversation__contact_name', 'content']
    readonly_fields = ['id', 'message_id', 'created_at']
    inlines = [MessageAttachmentInline]
    
    fieldsets = (
        ('Conversa', {
            'fields': ('conversation', 'sender')
        }),
        ('Mensagem', {
            'fields': ('content', 'direction', 'status', 'is_internal')
        }),
        ('Evolution API', {
            'fields': ('message_id', 'evolution_status', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def get_contact(self, obj):
        """Retorna telefone do contato."""
        return obj.conversation.contact_phone
    get_contact.short_description = 'Contato'


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    """Admin para Anexos."""
    
    list_display = [
        'original_filename', 'mime_type', 'storage_type',
        'tenant', 'size_bytes', 'expires_at', 'created_at'
    ]
    list_filter = ['storage_type', 'tenant', 'created_at']
    search_fields = ['original_filename', 'message__conversation__contact_phone']
    readonly_fields = [
        'id', 'message', 'tenant', 'size_bytes', 'created_at',
        'is_expired', 'is_image', 'is_video', 'is_audio', 'is_document'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'message', 'tenant', 'original_filename', 'mime_type')
        }),
        ('Storage', {
            'fields': ('storage_type', 'file_path', 'file_url', 'size_bytes', 'expires_at')
        }),
        ('Thumbnail', {
            'fields': ('thumbnail_path',),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('is_expired', 'is_image', 'is_video', 'is_audio', 'is_document', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BusinessHours)
class BusinessHoursAdmin(admin.ModelAdmin):
    """Admin para Horários de Atendimento."""
    
    list_display = ['tenant', 'department', 'timezone', 'is_active', 'created_at']
    list_filter = ['is_active', 'tenant', 'created_at']
    search_fields = ['tenant__name', 'department__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'department', 'timezone', 'is_active')
        }),
        ('Segunda-feira', {
            'fields': ('monday_enabled', 'monday_start', 'monday_end')
        }),
        ('Terça-feira', {
            'fields': ('tuesday_enabled', 'tuesday_start', 'tuesday_end')
        }),
        ('Quarta-feira', {
            'fields': ('wednesday_enabled', 'wednesday_start', 'wednesday_end')
        }),
        ('Quinta-feira', {
            'fields': ('thursday_enabled', 'thursday_start', 'thursday_end')
        }),
        ('Sexta-feira', {
            'fields': ('friday_enabled', 'friday_start', 'friday_end')
        }),
        ('Sábado', {
            'fields': ('saturday_enabled', 'saturday_start', 'saturday_end')
        }),
        ('Domingo', {
            'fields': ('sunday_enabled', 'sunday_start', 'sunday_end')
        }),
        ('Feriados', {
            'fields': ('holidays',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AfterHoursMessage)
class AfterHoursMessageAdmin(admin.ModelAdmin):
    """Admin para Mensagens Fora de Horário."""
    
    list_display = ['tenant', 'department', 'is_active', 'created_at']
    list_filter = ['is_active', 'tenant', 'created_at']
    search_fields = ['tenant__name', 'department__name', 'message_template']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'department', 'is_active')
        }),
        ('Mensagem', {
            'fields': ('message_template',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AfterHoursTaskConfig)
class AfterHoursTaskConfigAdmin(admin.ModelAdmin):
    """Admin para Configuração de Tarefas Fora de Horário."""
    
    list_display = ['tenant', 'department', 'create_task_enabled', 'task_priority', 'is_active']
    list_filter = ['is_active', 'create_task_enabled', 'task_priority', 'tenant', 'created_at']
    search_fields = ['tenant__name', 'department__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'tenant', 'department', 'is_active')
        }),
        ('Configuração de Tarefa', {
            'fields': (
                'create_task_enabled',
                'task_title_template',
                'task_description_template',
                'task_priority',
                'task_due_date_offset_hours',
                'task_type',
                'include_message_preview'
            )
        }),
        ('Atribuição', {
            'fields': ('auto_assign_to_department', 'auto_assign_to_agent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

