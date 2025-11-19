#!/usr/bin/env python
"""
Script para corrigir permissões do admin@alreasense.com
Execute via Railway Dashboard: Shell > python backend/fix_admin_permissions.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def fix_admin_permissions():
    print(f"\n{'='*60}")
    print('🔧 CORRIGINDO PERMISSÕES DO ADMIN')
    print(f"{'='*60}\n")
    
    ADMIN_EMAIL = 'admin@alreasense.com'
    
    # Buscar usuário admin
    admin_user = User.objects.filter(email=ADMIN_EMAIL).first()
    
    if not admin_user:
        print(f"❌ Usuário {ADMIN_EMAIL} não encontrado!")
        return
    
    print(f"👤 Usuário encontrado: {admin_user.email}")
    print(f"\n📋 Permissões ATUAIS:")
    print(f"   - is_superuser: {admin_user.is_superuser}")
    print(f"   - is_staff: {admin_user.is_staff}")
    print(f"   - is_active: {admin_user.is_active}")
    print(f"   - role: {admin_user.role}")
    
    # Corrigir permissões
    print(f"\n🔄 Corrigindo permissões...")
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.is_active = True
    admin_user.role = 'admin'
    admin_user.save()
    
    print(f"\n✅ Permissões CORRIGIDAS:")
    print(f"   - is_superuser: {admin_user.is_superuser} ✅")
    print(f"   - is_staff: {admin_user.is_staff} ✅")
    print(f"   - is_active: {admin_user.is_active} ✅")
    print(f"   - role: {admin_user.role} ✅")
    
    print(f"\n{'='*60}")
    print("✅ CORREÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"\n🎉 Agora {ADMIN_EMAIL} tem todas as permissões de admin!")

if __name__ == '__main__':
    fix_admin_permissions()

