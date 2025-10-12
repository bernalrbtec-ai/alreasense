"""
Criar usuário admin para tenant existente
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

# Buscar tenant RBTec
tenant = Tenant.objects.get(name='RBTec Informática')

# Criar usuário admin
user = User.objects.create(
    email='paulo@rbtec.com',
    username='paulo@rbtec.com',
    first_name='Paulo',
    last_name='Admin',
    tenant=tenant,
    role='admin',
    is_active=True,
    is_staff=False,
    is_superuser=False,
    notify_email=True,
    notify_whatsapp=False,
)

user.set_password('senha123')
user.save()

print(f"✅ Usuário criado com sucesso!")
print(f"   Email: {user.email}")
print(f"   Senha: senha123")
print(f"   Tenant: {tenant.name}")


