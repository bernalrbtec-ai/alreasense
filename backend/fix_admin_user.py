#!/usr/bin/env python
"""
Script para corrigir o admin do sistema:
- Promover paulo.bernal@alrea.ai a superuser
- Remover/desativar admin@alreasense.com
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

def fix_admin_user():
    print(f"\n{'='*60}")
    print('🔧 CORRIGINDO ADMIN DO SISTEMA')
    print(f"{'='*60}\n")
    
    # Email correto do admin
    CORRECT_ADMIN_EMAIL = 'paulo.bernal@alrea.ai'
    OLD_ADMIN_EMAIL = 'admin@alreasense.com'
    
    # 1. Verificar se paulo.bernal@alrea.ai existe
    print(f"1️⃣ Verificando usuário {CORRECT_ADMIN_EMAIL}...")
    correct_admin = User.objects.filter(email=CORRECT_ADMIN_EMAIL).first()
    
    if not correct_admin:
        print(f"   ⚠️  Usuário {CORRECT_ADMIN_EMAIL} não encontrado!")
        print(f"   📝 Criando novo usuário...")
        
        # Buscar tenant padrão
        tenant = Tenant.objects.filter(name='Default Tenant').first()
        if not tenant:
            tenant = Tenant.objects.first()
            if not tenant:
                print(f"   ❌ Nenhum tenant encontrado! Criando tenant padrão...")
                from apps.billing.models import Plan
                starter_plan = Plan.objects.filter(slug='starter').first()
                tenant = Tenant.objects.create(
                    name='Default Tenant',
                    current_plan=starter_plan,
                    ui_access=True
                )
                print(f"   ✅ Tenant criado: {tenant.name}")
        
        # Criar usuário
        correct_admin = User.objects.create_user(
            username=CORRECT_ADMIN_EMAIL,
            email=CORRECT_ADMIN_EMAIL,
            password='admin123',  # Senha padrão (usuário pode alterar depois)
            first_name='Paulo',
            last_name='Bernal',
            tenant=tenant,
            is_superuser=True,
            is_staff=True,
            is_active=True,
            role='admin'
        )
        print(f"   ✅ Usuário criado: {correct_admin.email}")
    else:
        print(f"   ✅ Usuário encontrado: {correct_admin.email}")
    
    # 2. Promover paulo.bernal@alrea.ai a superuser
    print(f"\n2️⃣ Promovendo {CORRECT_ADMIN_EMAIL} a superuser...")
    correct_admin.is_superuser = True
    correct_admin.is_staff = True
    correct_admin.is_active = True
    correct_admin.role = 'admin'
    correct_admin.save()
    print(f"   ✅ Permissões atualizadas:")
    print(f"      - is_superuser: {correct_admin.is_superuser}")
    print(f"      - is_staff: {correct_admin.is_staff}")
    print(f"      - role: {correct_admin.role}")
    
    # 3. Remover ou desativar admin@alreasense.com
    print(f"\n3️⃣ Verificando usuário {OLD_ADMIN_EMAIL}...")
    old_admin = User.objects.filter(email=OLD_ADMIN_EMAIL).first()
    
    if old_admin:
        print(f"   ⚠️  Usuário {OLD_ADMIN_EMAIL} encontrado!")
        
        # Se for o mesmo usuário (caso email foi alterado), não fazer nada
        if old_admin.id == correct_admin.id:
            print(f"   ℹ️  É o mesmo usuário (email foi alterado), mantendo...")
        else:
            # Remover permissões de superuser
            print(f"   🔄 Removendo permissões de superuser...")
            old_admin.is_superuser = False
            old_admin.is_staff = False
            old_admin.is_active = False  # Desativar ao invés de deletar
            old_admin.save()
            print(f"   ✅ Usuário {OLD_ADMIN_EMAIL} desativado")
            print(f"      - is_superuser: {old_admin.is_superuser}")
            print(f"      - is_staff: {old_admin.is_staff}")
            print(f"      - is_active: {old_admin.is_active}")
    else:
        print(f"   ✅ Usuário {OLD_ADMIN_EMAIL} não existe")
    
    # 4. Resumo final
    print(f"\n{'='*60}")
    print("✅ CORREÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"\n📋 Admin do sistema:")
    print(f"   Email: {correct_admin.email}")
    print(f"   Nome: {correct_admin.get_full_name()}")
    print(f"   Tenant: {correct_admin.tenant.name if correct_admin.tenant else 'N/A'}")
    print(f"   Permissões: Superuser ✅ | Staff ✅ | Active ✅")
    print(f"\n🎉 Agora você pode acessar com {CORRECT_ADMIN_EMAIL}")

if __name__ == '__main__':
    fix_admin_user()

