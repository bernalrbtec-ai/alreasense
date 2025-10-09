from django.db import models
from django.core.validators import RegexValidator
import uuid


phone_validator = RegexValidator(
    regex=r'^\+?[1-9]\d{1,14}$',
    message="Número deve estar no formato internacional: +5511999999999"
)


class Contact(models.Model):
    """Contato para campanhas"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, related_name='contacts')
    
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField(blank=True)
    
    # Campos customizados
    quem_indicou = models.CharField(max_length=200, blank=True, help_text="Quem indicou este contato")
    tags = models.JSONField(default=list, blank=True, help_text="Tags para segmentação")
    custom_vars = models.JSONField(default=dict, blank=True, help_text="Variáveis personalizadas")
    
    # Metadata
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contacts_contact'
        verbose_name = 'Contato'
        verbose_name_plural = 'Contatos'
        ordering = ['name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'phone']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'phone'],
                name='unique_phone_per_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.phone})"


class ContactGroup(models.Model):
    """Grupo de contatos para facilitar gestão"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE, related_name='contact_groups')
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    contacts = models.ManyToManyField(Contact, related_name='groups', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contacts_group'
        verbose_name = 'Grupo de Contatos'
        verbose_name_plural = 'Grupos de Contatos'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.contacts.count()} contatos)"

