from django.db import models
from apps.tenancy.models import Tenant


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
