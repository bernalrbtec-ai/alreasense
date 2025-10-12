"""
Criar todos os usuários de uma vez
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.billing.models import Plan

User = get_user_model()

print("\n" + "="*60)
print("🚀 CRIANDO ESTRUTURA COMPLETA")
print("="*60)

# 1. Criar Admin Tenant
print("\n1️⃣ Criando Admin Tenant...")
admin_tenant, created = Tenant.objects.get_or_create(
    name='Admin Tenant',
    defaults={'status': 'active'}
)
if created:
    print(f"   ✅ Admin Tenant criado: {admin_tenant.id}")
else:
    print(f"   ℹ️  Admin Tenant já existe: {admin_tenant.id}")

# Atribuir plano Starter
try:
    starter_plan = Plan.objects.get(slug='starter')
    admin_tenant.current_plan = starter_plan
    admin_tenant.save()
    print(f"   ✅ Plano Starter atribuído")
except Plan.DoesNotExist:
    print(f"   ⚠️  Plano Starter não encontrado")

# 2. Criar Super Admin
print("\n2️⃣ Criando Super Admin...")
superadmin, created = User.objects.get_or_create(
    email='superadmin@alreasense.com',
    defaults={
        'username': 'superadmin@alreasense.com',
        'first_name': 'Super',
        'last_name': 'Admin',
        'tenant': admin_tenant,
        'role': 'superadmin',
        'is_active': True,
        'is_staff': True,
        'is_superuser': True,
    }
)
if created:
    superadmin.set_password('admin123')
    superadmin.save()
    print(f"   ✅ Super Admin criado")
    print(f"   📧 Email: superadmin@alreasense.com")
    print(f"   🔐 Senha: admin123")
else:
    superadmin.username = 'superadmin@alreasense.com'
    superadmin.role = 'superadmin'
    superadmin.set_password('admin123')
    superadmin.save()
    print(f"   ℹ️  Super Admin atualizado")

# 3. Criar RBTec Tenant
print("\n3️⃣ Criando RBTec Tenant...")
rbtec_tenant, created = Tenant.objects.get_or_create(
    name='RBTec Informática',
    defaults={'status': 'active'}
)
if created:
    print(f"   ✅ RBTec Tenant criado: {rbtec_tenant.id}")
else:
    print(f"   ℹ️  RBTec Tenant já existe: {rbtec_tenant.id}")

# Atribuir plano Pro
try:
    pro_plan = Plan.objects.get(slug='pro')
    rbtec_tenant.current_plan = pro_plan
    rbtec_tenant.save()
    print(f"   ✅ Plano Pro atribuído")
except Plan.DoesNotExist:
    print(f"   ⚠️  Plano Pro não encontrado")

# 4. Criar Admin do RBTec
print("\n4️⃣ Criando Admin do RBTec...")
rbtec_admin, created = User.objects.get_or_create(
    email='paulo@rbtec.com',
    defaults={
        'username': 'paulo@rbtec.com',
        'first_name': 'Paulo',
        'last_name': 'Admin',
        'tenant': rbtec_tenant,
        'role': 'admin',
        'is_active': True,
        'is_staff': False,
        'is_superuser': False,
    }
)
if created:
    rbtec_admin.set_password('senha123')
    rbtec_admin.save()
    print(f"   ✅ Admin RBTec criado")
    print(f"   📧 Email: paulo@rbtec.com")
    print(f"   🔐 Senha: senha123")
else:
    rbtec_admin.username = 'paulo@rbtec.com'
    rbtec_admin.role = 'admin'
    rbtec_admin.set_password('senha123')
    rbtec_admin.save()
    print(f"   ℹ️  Admin RBTec atualizado")

print("\n" + "="*60)
print("✅ ESTRUTURA COMPLETA CRIADA!")
print("="*60)

print("\n📋 CREDENCIAIS:")
print("\n🔴 SUPER ADMIN:")
print("   Email: superadmin@alreasense.com")
print("   Senha: admin123")

print("\n🟡 ADMIN RBTEC:")
print("   Email: paulo@rbtec.com")
print("   Senha: senha123")

print("\n" + "="*60 + "\n")


