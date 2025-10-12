"""
Teste completo de login
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

print("\n" + "="*60)
print("🔍 TESTE COMPLETO DE LOGIN")
print("="*60)

# Listar todos os usuários
print("\n📋 USUÁRIOS CADASTRADOS:")
for user in User.objects.all():
    print(f"\n  {'='*56}")
    print(f"  Email: {user.email}")
    print(f"  Username: {user.username}")
    print(f"  Nome: {user.first_name} {user.last_name}")
    print(f"  Role: {user.role}")
    print(f"  Ativo: {user.is_active}")
    print(f"  Superuser: {user.is_superuser}")
    print(f"  Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")
    print(f"  Has usable password: {user.has_usable_password()}")

print("\n" + "="*60)
print("🧪 TESTANDO AUTENTICAÇÃO")
print("="*60)

# Teste 1: superadmin@alreasense.com com admin123
print("\n1️⃣ Teste: superadmin@alreasense.com / admin123")
user = authenticate(username='superadmin@alreasense.com', password='admin123')
if user:
    print(f"   ✅ SUCESSO! Autenticado como: {user.email}")
    token = RefreshToken.for_user(user)
    print(f"   🔑 Access Token: {str(token.access_token)[:50]}...")
else:
    print(f"   ❌ FALHOU")
    # Testar manualmente
    try:
        u = User.objects.get(email='superadmin@alreasense.com')
        print(f"   📝 Usuário existe: {u.email}")
        print(f"   🔐 Check password: {u.check_password('admin123')}")
        if not u.check_password('admin123'):
            print(f"   💡 Resetando senha...")
            u.set_password('admin123')
            u.save()
            user = authenticate(username='superadmin@alreasense.com', password='admin123')
            if user:
                print(f"   ✅ SUCESSO após resetar!")
    except User.DoesNotExist:
        print(f"   ❌ Usuário não existe!")

# Teste 2: paulo@rbtec.com com senha123
print("\n2️⃣ Teste: paulo@rbtec.com / senha123")
user = authenticate(username='paulo@rbtec.com', password='senha123')
if user:
    print(f"   ✅ SUCESSO! Autenticado como: {user.email}")
    token = RefreshToken.for_user(user)
    print(f"   🔑 Access Token: {str(token.access_token)[:50]}...")
else:
    print(f"   ❌ FALHOU")
    try:
        u = User.objects.get(email='paulo@rbtec.com')
        print(f"   📝 Usuário existe: {u.email}")
        print(f"   🔐 Check password: {u.check_password('senha123')}")
        if not u.check_password('senha123'):
            print(f"   💡 Resetando senha...")
            u.set_password('senha123')
            u.save()
            user = authenticate(username='paulo@rbtec.com', password='senha123')
            if user:
                print(f"   ✅ SUCESSO após resetar!")
    except User.DoesNotExist:
        print(f"   ❌ Usuário não existe!")

# Teste 3: admin@alreasense.com com senha123
print("\n3️⃣ Teste: admin@alreasense.com / senha123")
user = authenticate(username='admin@alreasense.com', password='senha123')
if user:
    print(f"   ✅ SUCESSO! Autenticado como: {user.email}")
    token = RefreshToken.for_user(user)
    print(f"   🔑 Access Token: {str(token.access_token)[:50]}...")
else:
    print(f"   ❌ FALHOU")
    try:
        u = User.objects.get(email='admin@alreasense.com')
        print(f"   📝 Usuário existe: {u.email}")
        print(f"   🔐 Check password: {u.check_password('senha123')}")
        if not u.check_password('senha123'):
            print(f"   💡 Resetando senha...")
            u.set_password('senha123')
            u.save()
            user = authenticate(username='admin@alreasense.com', password='senha123')
            if user:
                print(f"   ✅ SUCESSO após resetar!")
    except User.DoesNotExist:
        print(f"   ❌ Usuário não existe!")

print("\n" + "="*60)
print("✅ TESTE COMPLETO!")
print("="*60 + "\n")


