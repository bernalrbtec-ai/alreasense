"""
Corrigir usernames para serem iguais ao email
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*60)
print("🔧 CORRIGINDO USERNAMES")
print("="*60)

for user in User.objects.all():
    if user.username != user.email:
        print(f"\n📝 Atualizando: {user.email}")
        print(f"   Username antigo: {user.username}")
        user.username = user.email
        user.save()
        print(f"   Username novo: {user.username}")
        print(f"   ✅ Atualizado!")

print("\n" + "="*60)
print("📋 CREDENCIAIS FINAIS:")
print("="*60)

for user in User.objects.all():
    print(f"\n{'='*60}")
    if user.role == 'superadmin':
        print(f"🔴 SUPER ADMIN (Sistema)")
        print(f"   Email/Login: {user.email}")
        print(f"   Senha: admin123")
    elif user.role == 'admin':
        print(f"🟡 ADMIN (Cliente: {user.tenant.name if user.tenant else 'N/A'})")
        print(f"   Email/Login: {user.email}")
        print(f"   Senha: senha123")
    else:
        print(f"🟢 USER")
        print(f"   Email/Login: {user.email}")

print("\n" + "="*60 + "\n")


