"""
Admin para o módulo de contatos
"""

from django.contrib import admin
from .models import Contact, Tag, ContactList, ContactImport


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'tenant', 'lifecycle_stage', 'is_active', 'opted_out', 'created_at']
    list_filter = ['is_active', 'opted_out', 'source', 'gender', 'created_at']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = [
        'id', 'created_at', 'updated_at',
        'total_messages_received', 'total_messages_sent',
        'total_campaigns_participated', 'total_campaigns_responded'
    ]
    
    fieldsets = (
        ('Identificação', {
            'fields': ('id', 'tenant', 'phone', 'name', 'email')
        }),
        ('Dados Demográficos', {
            'fields': ('birth_date', 'gender', 'city', 'state', 'country', 'zipcode')
        }),
        ('Dados Comerciais', {
            'fields': (
                'last_purchase_date', 'last_purchase_value', 'total_purchases',
                'average_ticket', 'lifetime_value', 'last_visit_date'
            )
        }),
        ('Engajamento', {
            'fields': (
                'last_interaction_date',
                'total_messages_received', 'total_messages_sent',
                'total_campaigns_participated', 'total_campaigns_responded'
            )
        }),
        ('Observações', {
            'fields': ('notes', 'custom_fields')
        }),
        ('Controle', {
            'fields': ('is_active', 'opted_out', 'opted_out_at', 'source')
        }),
        ('Metadados', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'tenant', 'contact_count', 'created_at']
    list_filter = ['tenant', 'created_at']
    search_fields = ['name', 'description']


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active', 'contact_count', 'created_at']
    list_filter = ['is_active', 'tenant', 'created_at']
    search_fields = ['name', 'description']


@admin.register(ContactImport)
class ContactImportAdmin(admin.ModelAdmin):
    list_display = [
        'file_name', 'tenant', 'status',
        'total_rows', 'created_count', 'updated_count', 'error_count',
        'success_rate', 'created_at'
    ]
    list_filter = ['status', 'tenant', 'created_at']
    readonly_fields = [
        'id', 'file_name', 'file_path', 'status',
        'total_rows', 'processed_rows',
        'created_count', 'updated_count', 'skipped_count', 'error_count',
        'errors', 'created_at', 'completed_at'
    ]
    
    def success_rate(self, obj):
        return f"{obj.success_rate:.1f}%"
    success_rate.short_description = 'Taxa de Sucesso'
