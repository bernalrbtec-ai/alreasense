"""
Admin para Flow Chat.
"""
from django.contrib import admin
from apps.chat.models import Conversation, Message, MessageAttachment


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

