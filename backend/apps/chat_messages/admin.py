from django.contrib import admin
from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'chat_id', 'sender', 'text_preview', 'sentiment', 
        'satisfaction', 'created_at', 'has_analysis'
    ]
    list_filter = [
        'created_at', 'sentiment', 'satisfaction', 'emotion', 
        'tenant', 'connection'
    ]
    search_fields = ['text', 'chat_id', 'sender']
    readonly_fields = ['created_at', 'has_analysis', 'is_positive', 'is_satisfied']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message Content', {
            'fields': ('tenant', 'connection', 'chat_id', 'sender', 'text')
        }),
        ('AI Analysis', {
            'fields': (
                'sentiment', 'emotion', 'satisfaction', 'tone', 'summary',
                'has_analysis', 'is_positive', 'is_satisfied'
            )
        }),
        ('Vector Embedding', {
            'fields': ('embedding',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def text_preview(self, obj):
        """Show text preview in admin list."""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Text Preview'
    
    def has_analysis(self, obj):
        """Show if message has AI analysis."""
        return obj.has_analysis
    has_analysis.boolean = True
    has_analysis.short_description = 'Has Analysis'
