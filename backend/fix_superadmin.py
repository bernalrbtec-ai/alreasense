"""
Corrigir role do superadmin
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*60)
print("🔧 CORRIGINDO SUPERADMIN")
print("="*60)

# Atualizar superadmin
try:
    superadmin = User.objects.get(email='superadmin@alreasense.com')
    superadmin.role = 'superadmin'
    superadmin.is_superuser = True
    superadmin.is_staff = True
    superadmin.set_password('admin123')
    superadmin.save()
    print(f"\n✅ Superadmin atualizado:")
    print(f"   Email: {superadmin.email}")
    print(f"   Role: {superadmin.role}")
    print(f"   Senha: admin123")
except User.DoesNotExist:
    print(f"\n❌ Superadmin não encontrado")

# Atualizar admin do tenant Admin
try:
    admin = User.objects.get(email='admin@alreasense.com')
    admin.role = 'admin'
    admin.is_superuser = False
    admin.is_staff = False
    admin.set_password('senha123')
    admin.save()
    print(f"\n✅ Admin do tenant atualizado:")
    print(f"   Email: {admin.email}")
    print(f"   Role: {admin.role}")
    print(f"   Senha: senha123")
except User.DoesNotExist:
    print(f"\n❌ Admin não encontrado")

# Listar todos os usuários
print(f"\n" + "="*60)
print("📋 TODOS OS USUÁRIOS:")
print("="*60)

for user in User.objects.all():
    print(f"\n{user.email}")
    print(f"  Role: {user.role}")
    print(f"  Superuser: {user.is_superuser}")
    print(f"  Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")

print("\n" + "="*60 + "\n")


