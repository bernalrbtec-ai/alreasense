"""
Verificar e corrigir senhas dos usuários
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model, authenticate

User = get_user_model()

print("\n" + "="*60)
print("🔍 VERIFICANDO E CORRIGINDO USUÁRIOS")
print("="*60)

users = User.objects.all()

for user in users:
    print(f"\n{'='*60}")
    print(f"👤 Usuário: {user.first_name} {user.last_name}")
    print(f"   Email: {user.email}")
    print(f"   Username: {user.username}")
    print(f"   Ativo: {user.is_active}")
    print(f"   Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")
    
    # Resetar senha para 'senha123'
    user.set_password('senha123')
    user.is_active = True
    user.save()
    print(f"   ✅ Senha resetada para: senha123")
    print(f"   ✅ Usuário ativado")
    
    # Testar autenticação
    print(f"\n   🔐 Testando autenticação...")
    
    # Teste 1: Com username
    auth_user = authenticate(username=user.username, password='senha123')
    if auth_user:
        print(f"   ✅ Autenticação OK com username: {user.username}")
    else:
        print(f"   ❌ Autenticação FALHOU com username: {user.username}")
    
    # Teste 2: Com email (se diferente do username)
    if user.email != user.username:
        # Tentar encontrar pelo email
        try:
            user_by_email = User.objects.get(email=user.email)
            auth_user = authenticate(username=user_by_email.username, password='senha123')
            if auth_user:
                print(f"   ✅ Autenticação OK com email->username: {user.email}")
            else:
                print(f"   ❌ Autenticação FALHOU com email->username: {user.email}")
        except User.DoesNotExist:
            print(f"   ❌ Usuário não encontrado pelo email: {user.email}")

print("\n" + "="*60)
print("📝 RESUMO DE CREDENCIAIS")
print("="*60)

for user in User.objects.all():
    print(f"\n{'='*60}")
    print(f"Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")
    print(f"Nome: {user.first_name} {user.last_name}")
    print(f"Email para login: {user.email}")
    print(f"Senha: senha123")
    print(f"Role: {user.role}")
    print(f"Superuser: {user.is_superuser}")

print("\n" + "="*60)
print("✅ Correção concluída!")
print("="*60 + "\n")


