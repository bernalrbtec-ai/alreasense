"""
Testar login com credenciais específicas
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model, authenticate

User = get_user_model()

print("\n" + "="*60)
print("🔍 TESTANDO LOGIN")
print("="*60)

# Testar com paulo.bernal@rbtec.com.br
email = 'paulo.bernal@rbtec.com.br'
password = 'Paulo@2508'

print(f"\n📧 Email: {email}")
print(f"🔐 Senha: {password}")

# Verificar se usuário existe
try:
    user = User.objects.get(email=email)
    print(f"\n✅ Usuário encontrado:")
    print(f"   Nome: {user.first_name} {user.last_name}")
    print(f"   Email: {user.email}")
    print(f"   Username: {user.username}")
    print(f"   Ativo: {user.is_active}")
    print(f"   Tenant: {user.tenant.name if user.tenant else 'Nenhum'}")
    
    # Testar autenticação
    print(f"\n🔐 Testando autenticação...")
    
    # Como USERNAME_FIELD = 'email', usamos o email diretamente
    auth_user = authenticate(username=email, password=password)
    
    if auth_user:
        print(f"✅ AUTENTICAÇÃO BEM-SUCEDIDA!")
        print(f"   Usuário: {auth_user.email}")
        print(f"   Tenant: {auth_user.tenant.name if auth_user.tenant else 'Nenhum'}")
    else:
        print(f"❌ AUTENTICAÇÃO FALHOU")
        print(f"   Verificando se a senha está correta...")
        
        if user.check_password(password):
            print(f"   ✅ Senha está correta")
            print(f"   ⚠️ Problema pode estar no authenticate()")
        else:
            print(f"   ❌ Senha está incorreta")
            print(f"   💡 Resetando senha para: {password}")
            user.set_password(password)
            user.save()
            
            # Testar novamente
            auth_user = authenticate(username=email, password=password)
            if auth_user:
                print(f"   ✅ Autenticação OK após resetar senha!")
            else:
                print(f"   ❌ Ainda não funciona")
    
except User.DoesNotExist:
    print(f"\n❌ Usuário não encontrado com email: {email}")
    print(f"\n📋 Usuários disponíveis:")
    for u in User.objects.all():
        print(f"   • {u.email} - {u.first_name} {u.last_name}")

print("\n" + "="*60 + "\n")


