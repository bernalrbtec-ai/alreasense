#!/usr/bin/env python
"""
Script para corrigir admin na Railway
Execute via Railway Dashboard: Shell > python backend/fix_admin_railway.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

def fix_admin():
    print(f"\n{'='*60}")
    print('🔧 CORRIGINDO ADMIN NA RAILWAY')
    print(f"{'='*60}\n")
    
    CORRECT_ADMIN_EMAIL = 'paulo.bernal@alrea.ai'
    OLD_ADMIN_EMAIL = 'admin@alreasense.com'
    
    # 1. Verificar/criar paulo.bernal@alrea.ai
    print(f"1️⃣ Verificando {CORRECT_ADMIN_EMAIL}...")
    correct_admin = User.objects.filter(email=CORRECT_ADMIN_EMAIL).first()
    
    if not correct_admin:
        print(f"   📝 Criando usuário...")
        tenant = Tenant.objects.filter(name='Default Tenant').first() or Tenant.objects.first()
        if not tenant:
            from apps.billing.models import Plan
            starter_plan = Plan.objects.filter(slug='starter').first()
            tenant = Tenant.objects.create(name='Default Tenant', current_plan=starter_plan, ui_access=True)
        
        correct_admin = User.objects.create_user(
            username=CORRECT_ADMIN_EMAIL,
            email=CORRECT_ADMIN_EMAIL,
            password='admin123',
            first_name='Paulo',
            last_name='Bernal',
            tenant=tenant,
            is_superuser=True,
            is_staff=True,
            is_active=True,
            role='admin'
        )
        print(f"   ✅ Criado: {correct_admin.email}")
    else:
        print(f"   ✅ Encontrado: {correct_admin.email}")
    
    # 2. Promover a superuser
    print(f"\n2️⃣ Promovendo {CORRECT_ADMIN_EMAIL}...")
    correct_admin.is_superuser = True
    correct_admin.is_staff = True
    correct_admin.is_active = True
    correct_admin.role = 'admin'
    correct_admin.save()
    print(f"   ✅ Superuser: {correct_admin.is_superuser}")
    print(f"   ✅ Staff: {correct_admin.is_staff}")
    print(f"   ✅ Role: {correct_admin.role}")
    
    # 3. Desativar admin@alreasense.com
    print(f"\n3️⃣ Verificando {OLD_ADMIN_EMAIL}...")
    old_admin = User.objects.filter(email=OLD_ADMIN_EMAIL).first()
    
    if old_admin and old_admin.id != correct_admin.id:
        print(f"   🔄 Desativando...")
        old_admin.is_superuser = False
        old_admin.is_staff = False
        old_admin.is_active = False
        old_admin.save()
        print(f"   ✅ Desativado")
    else:
        print(f"   ✅ Não existe ou é o mesmo usuário")
    
    # 4. Resumo
    print(f"\n{'='*60}")
    print("✅ CORREÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"\n📋 Admin do sistema:")
    print(f"   Email: {correct_admin.email}")
    print(f"   Nome: {correct_admin.get_full_name()}")
    print(f"   Tenant: {correct_admin.tenant.name if correct_admin.tenant else 'N/A'}")
    print(f"\n🎉 Acesse com: {CORRECT_ADMIN_EMAIL} / admin123")

if __name__ == '__main__':
    fix_admin()

