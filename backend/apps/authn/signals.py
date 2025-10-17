"""
Signals para o app authn.
Cria departamentos padrão automaticamente ao criar um novo Tenant.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.tenancy.models import Tenant
from .models import Department


@receiver(post_save, sender=Tenant)
def create_default_departments(sender, instance, created, **kwargs):
    """
    Signal que cria departamentos padrão quando um novo Tenant é criado.
    
    Departamentos criados:
    - Financeiro (cor: azul)
    - Comercial (cor: verde)
    - Suporte (cor: laranja)
    """
    if created:
        default_departments = [
            {
                'name': 'Financeiro',
                'color': '#3b82f6',  # Azul
                'ai_enabled': False
            },
            {
                'name': 'Comercial',
                'color': '#10b981',  # Verde
                'ai_enabled': False
            },
            {
                'name': 'Suporte',
                'color': '#f59e0b',  # Laranja
                'ai_enabled': True  # Suporte tem IA habilitada por padrão
            }
        ]
        
        departments_to_create = [
            Department(
                tenant=instance,
                name=dept['name'],
                color=dept['color'],
                ai_enabled=dept['ai_enabled']
            )
            for dept in default_departments
        ]
        
        Department.objects.bulk_create(departments_to_create)
        
        print(f"✅ [SIGNAL] Criados 3 departamentos padrão para o tenant: {instance.name}")

