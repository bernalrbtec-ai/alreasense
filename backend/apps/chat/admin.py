"""
Admin para Flow Chat.
"""
from django.contrib import admin
from django.utils.html import format_html

from apps.chat.models import Conversation, Message, MessageAttachment
from apps.chat.models_business_hours import BusinessHours, AfterHoursMessage, AfterHoursTaskConfig
from apps.chat.models_flow import Flow, FlowNode, FlowEdge


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


# ---------- Fluxos (lista/botões): apenas admin do tenant ----------

def _flow_admin_queryset(request, base_queryset, tenant_field='tenant'):
    """Restringe ao tenant do usuário; superuser vê todos. tenant_field: 'tenant' (Flow) ou 'flow__tenant' (FlowNode)."""
    if getattr(request.user, 'is_superuser', False):
        return base_queryset
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return base_queryset.none()
    return base_queryset.filter(**{tenant_field: tenant})


@admin.register(Flow)
class FlowAdmin(admin.ModelAdmin):
    """Admin para Fluxos. Apenas administradores do tenant veem os fluxos do seu tenant."""

    list_display = ['name', 'scope', 'department', 'tenant', 'is_active', 'created_at']
    list_filter = ['scope', 'is_active', 'tenant']
    search_fields = ['name', 'tenant__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_editable = ['is_active']

    fieldsets = (
        (None, {
            'fields': ('id', 'tenant', 'name', 'scope', 'department', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return _flow_admin_queryset(request, super().get_queryset(request)).select_related('tenant', 'department')

    def has_module_permission(self, request):
        if getattr(request.user, 'is_superuser', False):
            return True
        return getattr(request.user, 'role', None) == 'admin'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'tenant':
            tenant = getattr(request.user, 'tenant', None)
            if tenant and not getattr(request.user, 'is_superuser', False):
                from apps.tenancy.models import Tenant
                kwargs['queryset'] = Tenant.objects.filter(id=tenant.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class FlowNodeInline(admin.TabularInline):
    model = FlowNode
    extra = 0
    fields = ['name', 'node_type', 'order', 'is_start', 'body_text', 'button_text']
    show_change_link = True


@admin.register(FlowNode)
class FlowNodeAdmin(admin.ModelAdmin):
    """Nós do fluxo. Filtrado por tenant (apenas admin do tenant)."""

    list_display = ['name', 'flow', 'node_type', 'order', 'is_start', 'created_at']
    list_filter = ['node_type', 'is_start', 'flow__tenant']
    search_fields = ['name', 'flow__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_editable = ['order', 'is_start']

    fieldsets = (
        (None, {
            'fields': ('id', 'flow', 'node_type', 'name', 'order', 'is_start')
        }),
        ('Conteúdo', {
            'fields': ('body_text', 'button_text', 'header_text', 'footer_text', 'sections', 'buttons')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('flow', 'flow__tenant')
        return _flow_admin_queryset(request, qs, tenant_field='flow__tenant')

    def has_module_permission(self, request):
        if getattr(request.user, 'is_superuser', False):
            return True
        return getattr(request.user, 'role', None) == 'admin'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'flow':
            from apps.chat.models_flow import Flow
            base = Flow.objects.all()
            kwargs['queryset'] = _flow_admin_queryset(request, base).select_related('tenant')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(FlowEdge)
class FlowEdgeAdmin(admin.ModelAdmin):
    """Arestas do fluxo. Filtrado por tenant (apenas admin do tenant)."""

    list_display = ['from_node', 'option_id', 'to_node_or_action', 'target_department', 'target_action']
    list_filter = ['target_action', 'from_node__flow__tenant']
    search_fields = ['option_id', 'from_node__name', 'to_node__name']
    readonly_fields = ['id']
    list_editable = ['target_action']

    def to_node_or_action(self, obj):
        if obj.to_node_id:
            return format_html('→ Nó: {}', obj.to_node.name)
        if obj.target_department_id:
            return format_html('→ Depto: {}', obj.target_department.name)
        return '→ Encerrar'
    to_node_or_action.short_description = 'Destino'

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('from_node', 'from_node__flow', 'to_node', 'target_department')
        if getattr(request.user, 'is_superuser', False):
            return qs
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return qs.none()
        return qs.filter(from_node__flow__tenant=tenant)

    def has_module_permission(self, request):
        if getattr(request.user, 'is_superuser', False):
            return True
        return getattr(request.user, 'role', None) == 'admin'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'from_node':
            from apps.chat.models_flow import FlowNode
            base = FlowNode.objects.all().select_related('flow')
            if not getattr(request.user, 'is_superuser', False):
                tenant = getattr(request.user, 'tenant', None)
                if tenant:
                    base = base.filter(flow__tenant=tenant)
            kwargs['queryset'] = base
        elif db_field.name == 'to_node':
            from apps.chat.models_flow import FlowNode
            base = FlowNode.objects.all().select_related('flow')
            if not getattr(request.user, 'is_superuser', False):
                tenant = getattr(request.user, 'tenant', None)
                if tenant:
                    base = base.filter(flow__tenant=tenant)
            kwargs['queryset'] = base
        elif db_field.name == 'target_department':
            from apps.authn.models import Department
            tenant = getattr(request.user, 'tenant', None)
            if tenant and not getattr(request.user, 'is_superuser', False):
                kwargs['queryset'] = Department.objects.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
