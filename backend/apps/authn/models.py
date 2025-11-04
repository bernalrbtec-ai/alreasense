from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.tenancy.models import Tenant
import uuid


class Department(models.Model):
    """
    Departamento dentro de um Tenant.
    Permite organizar usuários por áreas (Financeiro, Comercial, Suporte, etc).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='departments',
        verbose_name='Tenant'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Nome do Departamento',
        help_text='Ex: Financeiro, Comercial, Suporte'
    )
    color = models.CharField(
        max_length=7,
        default='#3b82f6',
        verbose_name='Cor (Hex)',
        help_text='Cor em hexadecimal para identificação visual (ex: #3b82f6)'
    )
    ai_enabled = models.BooleanField(
        default=False,
        verbose_name='IA Habilitada',
        help_text='Se este departamento tem recursos de IA habilitados'
    )
    transfer_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mensagem de Transferência',
        help_text='Mensagem automática enviada ao cliente quando uma conversa é transferida para este departamento'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        db_table = 'authn_department'
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        unique_together = [['tenant', 'name']]
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class User(AbstractUser):
    """Custom User model with tenant and role."""
    
    ROLE_CHOICES = [
        ('admin', 'Administrador'),       # Admin do tenant (acesso total)
        ('gerente', 'Gerente'),           # Gerente de departamento (métricas do depto)
        ('agente', 'Agente'),             # Agente (apenas chat do seu depto)
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
        default='agente'
    )
    departments = models.ManyToManyField(
        'Department',
        related_name='users',
        blank=True,
        verbose_name='Departamentos',
        help_text='Departamentos aos quais este usuário pertence'
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
        """Check if user is admin (acesso total ao tenant)."""
        return self.role == 'admin' or self.is_superuser
    
    @property
    def is_gerente(self):
        """Check if user is gerente (métricas do departamento)."""
        return self.role == 'gerente'
    
    @property
    def is_agente(self):
        """Check if user is agente (apenas chat)."""
        return self.role == 'agente'
    
    @property
    def is_operator(self):
        """Deprecated: mantido para compatibilidade."""
        return self.is_agente or self.is_gerente
    
    def can_access_all_departments(self):
        """Admin pode acessar todos os departamentos do tenant."""
        return self.is_admin
    
    def can_view_department_metrics(self, department=None):
        """Gerente pode ver métricas dos seus departamentos."""
        if self.is_admin:
            return True
        if self.is_gerente:
            if department is None:
                return self.departments.exists()
            return self.departments.filter(id=department.id).exists()
        return False
    
    def can_access_chat(self, department=None):
        """Agente e Gerente podem acessar chat dos seus departamentos."""
        if self.is_admin:
            return True
        if self.is_gerente or self.is_agente:
            if department is None:
                return self.departments.exists()
            return self.departments.filter(id=department.id).exists()
        return False
