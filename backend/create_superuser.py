#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.conf import settings
from apps.tenancy.models import Tenant

User = get_user_model()

def create_superuser():
    # Log database connection
    print(f"\n{'='*60}")
    print('🔧 CREATING SUPERUSER')
    print(f"{'='*60}")
    db_config = settings.DATABASES['default']
    print(f"Database: {db_config.get('NAME', 'N/A')}")
    print(f"Host: {db_config.get('HOST', 'N/A')}")
    
    # Test connection
    try:
        print("🔍 [SUPERUSER] Testando conexão com banco...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            print('✅ [SUPERUSER] Database connection OK\n')
    except Exception as e:
        print(f'❌ [SUPERUSER] Database connection failed: {e}\n')
        raise
    # Create default tenant if it doesn't exist
    print("🏢 [SUPERUSER] Verificando tenant padrão...")
    from apps.billing.models import Plan
    
    # Pegar plano Starter
    print("📋 [SUPERUSER] Buscando plano Starter...")
    starter_plan = Plan.objects.filter(slug='starter').first()
    if starter_plan:
        print(f"✅ [SUPERUSER] Plano encontrado: {starter_plan.name}")
    else:
        print("⚠️ [SUPERUSER] Plano Starter não encontrado!")
    
    print("🏢 [SUPERUSER] Criando/verificando tenant...")
    tenant, created = Tenant.objects.get_or_create(
        name='Default Tenant',
        defaults={
            'current_plan': starter_plan,
            'ui_access': True,
        }
    )
    
    if created:
        print(f"✅ [SUPERUSER] Tenant criado: {tenant.name}")
    else:
        print(f"✅ [SUPERUSER] Tenant existente: {tenant.name}")
    
    # Create superuser if it doesn't exist (check by role, not by specific email)
    print("👤 [SUPERUSER] Verificando superuser...")
    if not User.objects.filter(is_superuser=True).exists():
        print("👤 [SUPERUSER] Criando novo superuser...")
        user = User.objects.create_superuser(
            username='admin@alreasense.com',  # Use email as username
            email='admin@alreasense.com',
            password='admin123',
            tenant=tenant
        )
        print(f"✅ [SUPERUSER] Superuser criado: {user.email}")
    else:
        existing_superuser = User.objects.filter(is_superuser=True).first()
        print(f"✅ [SUPERUSER] Superuser já existe: {existing_superuser.email}")
    
    print("🎉 [SUPERUSER] Processo concluído com sucesso!")

if __name__ == '__main__':
    create_superuser()
