from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.tenancy.models import Tenant


class User(AbstractUser):
    """Custom User model with tenant and role."""
    
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),  # Admin do sistema
        ('admin', 'Admin'),              # Admin do cliente
        ('user', 'User'),                # Usuário do cliente
    ]
    
    # Override email to make it unique (required for USERNAME_FIELD)
    email = models.EmailField(
        unique=True,
        help_text="Email address (used for login)"
    )
    
    # Use email as username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='users'
    )
    role = models.CharField(
        max_length=16, 
        choices=ROLE_CHOICES, 
        default='user'
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        null=True, 
        blank=True,
        help_text="Avatar do usuário"
    )
    display_name = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Nome de exibição"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True,
        help_text="Telefone do usuário"
    )
    birth_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Data de nascimento"
    )
    notify_email = models.BooleanField(
        default=True,
        help_text="Receber notificações por e-mail"
    )
    notify_whatsapp = models.BooleanField(
        default=True,
        help_text="Receber notificações por WhatsApp"
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
