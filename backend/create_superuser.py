#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

def create_superuser():
    # Create default tenant if it doesn't exist
    tenant, created = Tenant.objects.get_or_create(
        name='Default Tenant',
        defaults={
            'plan': 'starter',
            'status': 'active',
        }
    )
    
    if created:
        print(f"Created tenant: {tenant.name}")
    else:
        print(f"Using existing tenant: {tenant.name}")
    
    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        user = User.objects.create_superuser(
            username='admin',
            email='admin@alreasense.com',
            password='admin123',
            tenant=tenant
        )
        print(f"Created superuser: {user.username}")
    else:
        print("Superuser already exists")

if __name__ == '__main__':
    create_superuser()
