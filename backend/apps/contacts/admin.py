from django.contrib import admin
from apps.contacts.models import Contact, ContactGroup


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'tenant', 'is_active', 'created_at']
    list_filter = ['is_active', 'tenant', 'created_at']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('tenant', 'name', 'phone', 'email')
        }),
        ('Informações Adicionais', {
            'fields': ('quem_indicou', 'tags', 'custom_vars', 'notes')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactGroup)
class ContactGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'contacts_count', 'created_at']
    list_filter = ['tenant', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['contacts']
    
    def contacts_count(self, obj):
        return obj.contacts.count()
    contacts_count.short_description = 'Contatos'

