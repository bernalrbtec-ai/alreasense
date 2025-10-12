#!/usr/bin/env python
"""
Script para verificar e corrigir login do usuário
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User

email = 'paulo.bernal@rbtec.com.br'
password = 'senha123'

print("\n" + "="*60)
print("🔧 VERIFICANDO E CORRIGINDO LOGIN DO USUÁRIO")
print("="*60)

user = User.objects.filter(email=email).first()

if not user:
    print(f"\n❌ Usuário {email} não encontrado!")
    print("\n📋 Listando todos os usuários:")
    for u in User.objects.all():
        print(f"   - {u.id} | {u.email} | {u.username} | {u.first_name} {u.last_name}")
    exit(1)

print(f"\n✅ Usuário encontrado:")
print(f"   ID: {user.id}")
print(f"   Email: {user.email}")
print(f"   Username: {user.username}")
print(f"   Nome: {user.first_name} {user.last_name}")
print(f"   Ativo: {user.is_active}")
print(f"   Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")

# Verificar senha atual
print(f"\n🔐 Verificando senha atual...")
password_check = user.check_password(password)
print(f"   Senha '{password}' está correta: {password_check}")

if not password_check:
    print(f"\n🔧 Corrigindo senha...")
    user.set_password(password)
    user.username = user.email  # Garantir que username = email
    user.save()
    print(f"   ✅ Senha atualizada para '{password}'")
    print(f"   ✅ Username atualizado para '{user.email}'")
    
    # Verificar novamente
    password_check_after = user.check_password(password)
    print(f"   ✅ Verificação pós-correção: {password_check_after}")
else:
    print(f"   ✅ Senha já está correta!")

# Verificar se username = email
if user.username != user.email:
    print(f"\n🔧 Corrigindo username...")
    user.username = user.email
    user.save()
    print(f"   ✅ Username atualizado para '{user.email}'")

print(f"\n{'='*60}")
print("✅ VERIFICAÇÃO CONCLUÍDA!")
print("="*60 + "\n")

