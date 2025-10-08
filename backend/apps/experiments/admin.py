from django.contrib import admin
from .models import PromptTemplate, Inference, ExperimentRun


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['version', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['version', 'description', 'body']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('version', 'description', 'is_active', 'created_by')
        }),
        ('Prompt Content', {
            'fields': ('body',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Inference)
class InferenceAdmin(admin.ModelAdmin):
    list_display = [
        'message', 'prompt_version', 'model_name', 'sentiment', 
        'satisfaction', 'is_shadow', 'run_id', 'created_at'
    ]
    list_filter = [
        'is_shadow', 'prompt_version', 'model_name', 'run_id', 'created_at'
    ]
    search_fields = ['message__text', 'run_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(ExperimentRun)
class ExperimentRunAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'run_id', 'prompt_version', 'status', 
        'progress_percentage', 'created_at'
    ]
    list_filter = ['status', 'prompt_version', 'created_at']
    search_fields = ['name', 'run_id', 'description']
    readonly_fields = ['created_at', 'progress_percentage']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'run_id', 'name', 'description')
        }),
        ('Experiment Details', {
            'fields': ('prompt_version', 'start_date', 'end_date', 'status')
        }),
        ('Progress', {
            'fields': ('total_messages', 'processed_messages', 'progress_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
