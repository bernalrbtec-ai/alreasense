#!/usr/bin/env python3
"""
Script para criar usuário admin e tenant
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.billing.models import Plan

User = get_user_model()

def create_admin_user():
    print("🚀 Criando usuário admin e tenant...")
    
    # Buscar plano Starter
    try:
        starter_plan = Plan.objects.get(slug='starter')
        print(f"✅ Plano encontrado: {starter_plan.name}")
    except Plan.DoesNotExist:
        print("❌ Plano Starter não encontrado. Execute o seed primeiro.")
        return
    
    # Criar tenant
    tenant, created = Tenant.objects.get_or_create(
        name='Admin Tenant',
        defaults={
            'current_plan': starter_plan,
            'status': 'active',
            'ui_access': True
        }
    )
    
    if created:
        print(f"✅ Tenant criado: {tenant.name}")
    else:
        print(f"✅ Tenant já existe: {tenant.name}")
    
    # Criar usuário admin
    user, created = User.objects.get_or_create(
        email='admin@alreasense.com',
        defaults={
            'username': 'admin',
            'first_name': 'Admin',
            'last_name': 'User',
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
            'tenant': tenant
        }
    )
    
    if created:
        user.set_password('admin123')
        user.save()
        print(f"✅ Usuário admin criado: {user.email}")
    else:
        print(f"✅ Usuário admin já existe: {user.email}")
        # Atualizar senha
        user.set_password('admin123')
        user.save()
        print("✅ Senha atualizada")
    
    print("\n🎉 Setup concluído!")
    print(f"📧 Email: admin@alreasense.com")
    print(f"🔑 Senha: admin123")
    print(f"🏢 Tenant: {tenant.name} ({tenant.current_plan.name})")

if __name__ == "__main__":
    create_admin_user()
