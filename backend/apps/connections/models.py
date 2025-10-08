import uuid
from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from apps.tenancy.models import Tenant


class EvolutionConnection(models.Model):
    """Evolution API connection configuration."""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evolution_connections')
    name = models.CharField(max_length=100)
    base_url = models.URLField(help_text="URL base da Evolution API")
    api_key = encrypt(models.CharField(max_length=255, help_text="API Key da Evolution API"))
    webhook_url = models.URLField(help_text="URL do webhook para receber eventos")
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    last_check = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'connections_evolutionconnection'
        verbose_name = 'Evolution Connection'
        verbose_name_plural = 'Evolution Connections'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.base_url})"
    
    @property
    def is_online(self):
        """Check if connection is online."""
        if not self.last_check:
            return False
        return self.status == 'active' and (timezone.now() - self.last_check).seconds < 300
    
    def update_status(self, status, error_message=None):
        """Update connection status."""
        self.status = status
        self.last_check = timezone.now()
        if error_message:
            self.last_error = error_message
        self.save(update_fields=['status', 'last_check', 'last_error'])