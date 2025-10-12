"""
Script para testar criação de tenant com usuário via API
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.billing.models import Plan

User = get_user_model()

def test_tenant_user():
    print("\n" + "="*60)
    print("🔍 VERIFICANDO TENANTS E USUÁRIOS")
    print("="*60)
    
    # Listar todos os tenants
    tenants = Tenant.objects.all()
    print(f"\n📊 Total de Tenants: {tenants.count()}")
    
    for tenant in tenants:
        print(f"\n{'='*60}")
        print(f"🏢 Tenant: {tenant.name}")
        print(f"   ID: {tenant.id}")
        print(f"   Status: {tenant.status}")
        print(f"   Plano: {tenant.current_plan.name if tenant.current_plan else 'Sem plano'}")
        
        # Buscar usuários deste tenant
        users = User.objects.filter(tenant=tenant)
        print(f"\n   👥 Usuários ({users.count()}):")
        
        for user in users:
            print(f"      • {user.first_name} {user.last_name}")
            print(f"        Email: {user.email}")
            print(f"        Username: {user.username}")
            print(f"        Role: {user.role}")
            print(f"        Ativo: {user.is_active}")
            print(f"        Staff: {user.is_staff}")
            print(f"        Superuser: {user.is_superuser}")
            print(f"        Notify Email: {user.notify_email}")
            print(f"        Notify WhatsApp: {user.notify_whatsapp}")
            
            # Testar senha
            print(f"\n        🔐 Testando autenticação...")
            from django.contrib.auth import authenticate
            
            # Tentar autenticar com username
            auth_user = authenticate(username=user.username, password='senha123')
            if auth_user:
                print(f"        ✅ Autenticação OK com username")
            else:
                print(f"        ❌ Autenticação FALHOU com username")
                print(f"        💡 Tentando resetar senha para 'senha123'...")
                user.set_password('senha123')
                user.save()
                auth_user = authenticate(username=user.username, password='senha123')
                if auth_user:
                    print(f"        ✅ Senha resetada com sucesso!")
                else:
                    print(f"        ❌ Ainda não consegue autenticar")
    
    print("\n" + "="*60)
    print("✅ Verificação concluída!")
    print("="*60 + "\n")

if __name__ == '__main__':
    test_tenant_user()


