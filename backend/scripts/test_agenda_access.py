"""
Script para testar acesso à agenda baseado em acesso ao chat.

Testa se usuários com acesso ao chat também têm acesso à agenda,
mesmo sem o produto workflow habilitado.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.authn.models import User
from apps.tenancy.models import Tenant
from apps.billing.models import Product, TenantProduct
from apps.authn.permissions import CanAccessAgenda
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request


def test_agenda_access():
    """Testa acesso à agenda para diferentes cenários"""
    
    print("🧪 Testando acesso à agenda...")
    print("=" * 60)
    
    # Criar request factory
    factory = APIRequestFactory()
    
    # Buscar um tenant de exemplo
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado. Crie um tenant primeiro.")
        return
    
    print(f"📋 Tenant: {tenant.name}")
    print()
    
    # Buscar usuários de diferentes roles
    admin = User.objects.filter(tenant=tenant, role='admin').first()
    gerente = User.objects.filter(tenant=tenant, role='gerente').first()
    agente = User.objects.filter(tenant=tenant, role='agente').first()
    
    if not admin:
        print("⚠️  Nenhum admin encontrado. Criando usuário de teste...")
        admin = User.objects.create_user(
            username='test_admin',
            email='admin@test.com',
            password='test123',
            tenant=tenant,
            role='admin'
        )
    
    if not gerente:
        print("⚠️  Nenhum gerente encontrado. Criando usuário de teste...")
        gerente = User.objects.create_user(
            username='test_gerente',
            email='gerente@test.com',
            password='test123',
            tenant=tenant,
            role='gerente'
        )
    
    if not agente:
        print("⚠️  Nenhum agente encontrado. Criando usuário de teste...")
        agente = User.objects.create_user(
            username='test_agente',
            email='agente@test.com',
            password='test123',
            tenant=tenant,
            role='agente'
        )
    
    # Verificar se tenant tem produto workflow
    workflow_product = Product.objects.filter(slug='workflow').first()
    has_workflow = False
    if workflow_product:
        tenant_workflow = TenantProduct.objects.filter(
            tenant=tenant,
            product=workflow_product,
            is_active=True
        ).first()
        has_workflow = tenant_workflow is not None
    
    print(f"📦 Tenant tem produto workflow: {has_workflow}")
    print()
    
    # Criar permissão
    permission = CanAccessAgenda()
    
    # Testar cada usuário
    users_to_test = [
        ('Admin', admin),
        ('Gerente', gerente),
        ('Agente', agente),
    ]
    
    for role_name, user in users_to_test:
        print(f"👤 Testando {role_name} ({user.email}):")
        
        # Criar request mock
        request = factory.get('/api/contacts/tasks/')
        request.user = user
        
        # Verificar acesso
        has_access = permission.has_permission(request, None)
        
        # Verificar acesso ao chat
        can_access_chat = user.is_admin or user.is_gerente or user.is_agente
        
        print(f"   - Acesso ao chat: {can_access_chat}")
        print(f"   - Acesso à agenda: {has_access}")
        
        if has_access:
            print(f"   ✅ {role_name} TEM acesso à agenda")
        else:
            print(f"   ❌ {role_name} NÃO TEM acesso à agenda")
        
        print()
    
    print("=" * 60)
    print("✅ Teste concluído!")
    print()
    print("📝 Resumo:")
    print("   - Usuários com acesso ao chat (admin, gerente, agente)")
    print("     devem ter acesso à agenda, mesmo sem produto workflow")
    print("   - Se não tiverem acesso ao chat, precisam do produto workflow")


if __name__ == '__main__':
    test_agenda_access()


