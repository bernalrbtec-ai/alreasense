"""
Script para criar departamentos padrão para tenants existentes.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.tenancy.models import Tenant
from apps.authn.models import Department


def create_departments_for_tenants():
    """Cria departamentos padrão para todos os tenants que não têm departamentos."""
    
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
    
    tenants = Tenant.objects.all()
    
    for tenant in tenants:
        existing_depts = Department.objects.filter(tenant=tenant).count()
        
        if existing_depts == 0:
            departments_to_create = [
                Department(
                    tenant=tenant,
                    name=dept['name'],
                    color=dept['color'],
                    ai_enabled=dept['ai_enabled']
                )
                for dept in default_departments
            ]
            
            Department.objects.bulk_create(departments_to_create)
            print(f"✅ Criados 3 departamentos padrão para o tenant: {tenant.name}")
        else:
            print(f"⏭️ Tenant {tenant.name} já tem {existing_depts} departamento(s)")
    
    print("\n✅ Processo concluído!")


if __name__ == '__main__':
    create_departments_for_tenants()

