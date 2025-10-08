from django.contrib import admin
from .models import Plan, PaymentAccount, BillingEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'billing_cycle_days', 'is_free', 'is_active', 'max_connections', 'max_messages_per_month']
    list_filter = ['is_active', 'is_free']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price', 'billing_cycle_days', 'is_free', 'stripe_price_id')
        }),
        ('Limits', {
            'fields': ('max_connections', 'max_messages_per_month')
        }),
        ('Features', {
            'fields': ('features',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'status', 'current_period_end', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['tenant__name', 'stripe_customer_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'status')
        }),
        ('Stripe Information', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'event_type', 'processed', 'created_at']
    list_filter = ['event_type', 'processed', 'created_at']
    search_fields = ['tenant__name', 'stripe_event_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('tenant', 'event_type', 'stripe_event_id', 'processed')
        }),
        ('Event Data', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
