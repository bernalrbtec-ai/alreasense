#!/usr/bin/env python
"""
Script para gerar hash de senha no formato Django para uso em SQL.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth.hashers import make_password

# Senha a ser hashada
PASSWORD = '123@qwe'
EMAIL = 'admin@alreasense.com'

# Gerar hash
password_hash = make_password(PASSWORD)

print("\n" + "="*80)
print("🔐 GERAÇÃO DE HASH DE SENHA - DJANGO")
print("="*80)
print(f"\n📧 Email: {EMAIL}")
print(f"🔑 Senha: {PASSWORD}")
print(f"\n📝 Hash gerado:")
print(f"   {password_hash}")
print("\n" + "="*80)
print("\n📋 SQL para atualizar a senha:")
print("-"*80)
print(f"""
-- Atualizar senha do usuário admin@alreasense.com
UPDATE authn_user
SET password = '{password_hash}'
WHERE email = '{EMAIL}';

-- Verificar se foi atualizado
SELECT id, email, username, is_active, is_superuser, is_staff
FROM authn_user
WHERE email = '{EMAIL}';
""")
print("="*80)




