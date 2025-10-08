from django.db import models
from apps.tenancy.models import Tenant
import uuid


class Plan(models.Model):
    """Subscription plans available for tenants."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_cycle_days = models.IntegerField(default=30, help_text="Billing cycle in days")
    is_free = models.BooleanField(default=False, help_text="Free plan (no billing)")
    max_connections = models.IntegerField(default=1, help_text="-1 for unlimited")
    max_messages_per_month = models.IntegerField(default=1000, help_text="-1 for unlimited")
    features = models.JSONField(default=list, help_text="List of features")
    is_active = models.BooleanField(default=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, help_text="Stripe Price ID")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_plan'
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - R$ {self.price}"


class PaymentAccount(models.Model):
    """Stripe payment account for tenants."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
    ]
    
    tenant = models.OneToOneField(
        Tenant, 
        on_delete=models.CASCADE,
        related_name='payment_account'
    )
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_paymentaccount'
        verbose_name = 'Payment Account'
        verbose_name_plural = 'Payment Accounts'
    
    def __str__(self):
        return f"{self.tenant.name} - {self.status}"


class BillingEvent(models.Model):
    """Track billing events and webhooks."""
    
    EVENT_TYPES = [
        ('invoice.paid', 'Invoice Paid'),
        ('invoice.payment_failed', 'Payment Failed'),
        ('customer.subscription.created', 'Subscription Created'),
        ('customer.subscription.updated', 'Subscription Updated'),
        ('customer.subscription.deleted', 'Subscription Deleted'),
        ('payment_method.attached', 'Payment Method Attached'),
    ]
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE,
        related_name='billing_events'
    )
    event_type = models.CharField(max_length=64, choices=EVENT_TYPES)
    stripe_event_id = models.CharField(max_length=255, unique=True)
    processed = models.BooleanField(default=False)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_billingevent'
        verbose_name = 'Billing Event'
        verbose_name_plural = 'Billing Events'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.tenant.name}"
