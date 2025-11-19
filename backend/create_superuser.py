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
    # ✅ CORREÇÃO: Usar paulo.bernal@alrea.ai como admin padrão
    ADMIN_EMAIL = 'paulo.bernal@alrea.ai'
    
    print("👤 [SUPERUSER] Verificando superuser...")
    if not User.objects.filter(is_superuser=True).exists():
        print("👤 [SUPERUSER] Criando novo superuser...")
        user = User.objects.create_superuser(
            username=ADMIN_EMAIL,  # Use email as username
            email=ADMIN_EMAIL,
            password='admin123',
            tenant=tenant,
            first_name='Paulo',
            last_name='Bernal',
            role='admin'
        )
        print(f"✅ [SUPERUSER] Superuser criado: {user.email}")
    else:
        existing_superuser = User.objects.filter(is_superuser=True).first()
        print(f"✅ [SUPERUSER] Superuser já existe: {existing_superuser.email}")
        
        # ✅ CORREÇÃO: Se o superuser existente não for paulo.bernal@alrea.ai, corrigir
        if existing_superuser.email != ADMIN_EMAIL:
            print(f"⚠️  [SUPERUSER] Superuser atual ({existing_superuser.email}) não é o correto!")
            print(f"🔄 [SUPERUSER] Verificando se {ADMIN_EMAIL} existe...")
            
            correct_admin = User.objects.filter(email=ADMIN_EMAIL).first()
            if correct_admin:
                print(f"✅ [SUPERUSER] Usuário {ADMIN_EMAIL} encontrado, promovendo...")
                correct_admin.is_superuser = True
                correct_admin.is_staff = True
                correct_admin.is_active = True
                correct_admin.role = 'admin'
                correct_admin.save()
                
                # Desativar admin antigo
                existing_superuser.is_superuser = False
                existing_superuser.is_staff = False
                existing_superuser.is_active = False
                existing_superuser.save()
                print(f"✅ [SUPERUSER] {ADMIN_EMAIL} promovido a superuser")
                print(f"✅ [SUPERUSER] {existing_superuser.email} desativado")
            else:
                print(f"⚠️  [SUPERUSER] {ADMIN_EMAIL} não existe, mantendo {existing_superuser.email}")
    
    print("🎉 [SUPERUSER] Processo concluído com sucesso!")

if __name__ == '__main__':
    create_superuser()
