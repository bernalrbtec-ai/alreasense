import uuid
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    """Tenant model for multi-tenancy."""
    
    PLAN_CHOICES = [
        ('starter', 'Starter'),
        ('pro', 'Pro'),
        ('scale', 'Scale'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('trial', 'Trial'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    plan = models.CharField(max_length=32, choices=PLAN_CHOICES, default='starter')
    next_billing_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenancy_tenant'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
    
    def __str__(self):
        return f"{self.name} ({self.plan})"
    
    @property
    def is_active(self):
        """Check if tenant is active."""
        return self.status == 'active'
    
    @property
    def plan_limits(self):
        """Get plan limits."""
        limits = {
            'starter': {'connections': 1, 'retention_days': 30, 'price': 199},
            'pro': {'connections': 3, 'retention_days': 180, 'price': 499},
            'scale': {'connections': 6, 'retention_days': 365, 'price': 999},
            'enterprise': {'connections': -1, 'retention_days': 730, 'price': 0},
        }
        return limits.get(self.plan, limits['starter'])
    
    def can_add_connection(self, current_count):
        """Check if tenant can add another connection."""
        limit = self.plan_limits['connections']
        return limit == -1 or current_count < limit
