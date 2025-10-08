from django.db import models
from django_cryptography.fields import encrypt
from apps.tenancy.models import Tenant


class EvolutionConnection(models.Model):
    """Evolution API connection model."""
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='connections'
    )
    name = models.CharField(max_length=80)
    evo_ws_url = models.URLField()
    evo_token = encrypt(models.CharField(max_length=255))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'connections_evolutionconnection'
        verbose_name = 'Evolution Connection'
        verbose_name_plural = 'Evolution Connections'
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def status(self):
        """Get connection status."""
        return "active" if self.is_active else "inactive"
