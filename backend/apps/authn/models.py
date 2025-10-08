from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.tenancy.models import Tenant


class User(AbstractUser):
    """Custom User model with tenant and role."""
    
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('operator', 'Operator'),
    ]
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='users'
    )
    role = models.CharField(
        max_length=16, 
        choices=ROLE_CHOICES, 
        default='operator'
    )
    
    class Meta:
        db_table = 'authn_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.username} ({self.tenant.name})"
    
    @property
    def is_admin(self):
        """Check if user is admin."""
        return self.role == 'admin'
    
    @property
    def is_operator(self):
        """Check if user is operator."""
        return self.role == 'operator'
