"""
BillingAPIKey - API Keys para acesso externo ao sistema de cobrança
"""
from django.db import models
from django.utils import timezone
import uuid
import secrets


class BillingAPIKey(models.Model):
    """
    API Key para acesso externo ao sistema de cobrança
    
    Permite que sistemas externos (ERPs, CRMs) enviem cobranças via API
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenancy.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_api_keys',
        verbose_name='Tenant'
    )
    
    # Identificação
    name = models.CharField(
        max_length=100,
        help_text='Nome descritivo da API Key (ex: "ERP Principal")'
    )
    
    # API Key (gerada automaticamente)
    key = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text='API Key (gerada automaticamente)'
    )
    
    # Permissões
    is_active = models.BooleanField(
        default=True,
        help_text='API Key ativa'
    )
    
    # Limites
    rate_limit_per_hour = models.IntegerField(
        default=100,
        help_text='Máximo de requisições por hora (0 = ilimitado)',
        null=True,
        blank=True
    )
    
    # IPs permitidos (opcional)
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text='Lista de IPs permitidos (vazio = todos)'
    )
    
    # Expiração
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data de expiração (null = nunca expira)'
    )
    
    # Último uso
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última vez que a API Key foi usada'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'billing'
        db_table = 'billing_api_key'
        verbose_name = 'API Key de Billing'
        verbose_name_plural = 'API Keys de Billing'
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.tenant.name}"
    
    def save(self, *args, **kwargs):
        """Gera API Key automaticamente se não existir"""
        if not self.key:
            self.key = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    def is_valid(self, ip_address=None):
        """
        Verifica se a API Key é válida
        
        Args:
            ip_address: IP do cliente (opcional, para validação)
        
        Returns:
            (is_valid, reason)
        """
        if not self.is_active:
            return False, "API Key inativa"
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False, "API Key expirada"
        
        # Verifica IP se configurado
        if self.allowed_ips and ip_address:
            if ip_address not in self.allowed_ips:
                return False, f"IP {ip_address} não autorizado"
        
        return True, ""
    
    def can_use_template_type(self, template_type):
        """Verifica se pode usar este tipo de template"""
        # Por enquanto, todas as keys podem usar todos os tipos
        # Pode ser expandido no futuro com campo allowed_template_types
        return True
    
    def increment_usage(self, ip_address=None):
        """Incrementa contador de uso"""
        self.last_used_at = timezone.now()
        if ip_address:
            # Poderia salvar em um campo last_used_ip se necessário
            pass
        self.save(update_fields=['last_used_at'])
    
    def update_last_used(self):
        """Atualiza timestamp de último uso (alias para compatibilidade)"""
        self.increment_usage()



