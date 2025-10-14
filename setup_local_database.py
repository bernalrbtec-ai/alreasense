#!/usr/bin/env python
"""
Script para configurar banco local com dados de teste
"""
import os
import sys
import django

# Adicionar o diretório backend ao path
sys.path.append('backend')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.tenancy.models import Tenant
from apps.authn.models import User
from apps.billing.models import Plan, Product, PlanProduct, TenantProduct
from apps.contacts.models import Contact, Tag, List
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

def create_test_data():
    print("="*80)
    print("🗄️ CONFIGURANDO BANCO LOCAL COM DADOS DE TESTE")
    print("="*80)
    
    # 1. Criar tenant de teste
    print("\n🏢 Criando tenant de teste...")
    tenant, created = Tenant.objects.get_or_create(
        name="Teste Local",
        defaults={
            'description': 'Tenant para testes locais',
        }
    )
    
    if created:
        print(f"   ✅ Tenant criado: {tenant.name}")
    else:
        print(f"   ✅ Tenant já existe: {tenant.name}")
    
    # 2. Criar usuário admin
    print("\n👤 Criando usuário admin...")
    admin_user, created = User.objects.get_or_create(
        email="admin@teste.local",
        defaults={
            'username': 'admin@teste.local',
            'first_name': 'Admin',
            'last_name': 'Teste',
            'tenant': tenant,
            'role': 'admin',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        }
    )
    
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"   ✅ Usuário admin criado: {admin_user.email} (senha: admin123)")
    else:
        print(f"   ✅ Usuário admin já existe: {admin_user.email}")
    
    # 3. Criar planos
    print("\n📋 Criando planos...")
    plans_data = [
        {
            'slug': 'teste-basico',
            'name': 'Teste Básico',
            'description': 'Plano para testes básicos',
            'price': 0.00,
            'color': '#10B981',
            'sort_order': 1,
            'is_active': True,
        },
        {
            'slug': 'teste-pro',
            'name': 'Teste Pro',
            'description': 'Plano para testes avançados',
            'price': 99.00,
            'color': '#3B82F6',
            'sort_order': 2,
            'is_active': True,
        },
    ]
    
    for plan_data in plans_data:
        plan, created = Plan.objects.get_or_create(
            slug=plan_data['slug'],
            defaults=plan_data
        )
        if created:
            print(f"   ✅ Plano criado: {plan.name}")
        else:
            print(f"   ✅ Plano já existe: {plan.name}")
    
    # 4. Criar produtos
    print("\n📦 Criando produtos...")
    products_data = [
        {
            'slug': 'flow',
            'name': 'ALREA Flow',
            'description': 'Sistema de campanhas WhatsApp',
            'requires_ui_access': True,
            'addon_price': None,
            'icon': 'message-square',
            'color': '#3B82F6',
            'is_active': True,
        },
        {
            'slug': 'notifications',
            'name': 'Notificações de Campanha',
            'description': 'Sistema de notificações em tempo real',
            'requires_ui_access': True,
            'addon_price': 29.00,
            'icon': 'bell',
            'color': '#10B981',
            'is_active': True,
        },
    ]
    
    for product_data in products_data:
        product, created = Product.objects.get_or_create(
            slug=product_data['slug'],
            defaults=product_data
        )
        if created:
            print(f"   ✅ Produto criado: {product.name}")
        else:
            print(f"   ✅ Produto já existe: {product.name}")
    
    # 5. Associar produtos aos planos
    print("\n🔗 Associando produtos aos planos...")
    
    # Plano básico: apenas flow
    basic_plan = Plan.objects.get(slug='teste-basico')
    flow_product = Product.objects.get(slug='flow')
    
    plan_product, created = PlanProduct.objects.get_or_create(
        plan=basic_plan,
        product=flow_product,
        defaults={
            'is_included': True,
            'is_addon_available': False,
        }
    )
    if created:
        print(f"   ✅ {flow_product.name} associado ao {basic_plan.name}")
    
    # Plano pro: flow + notifications
    pro_plan = Plan.objects.get(slug='teste-pro')
    notifications_product = Product.objects.get(slug='notifications')
    
    for product in [flow_product, notifications_product]:
        plan_product, created = PlanProduct.objects.get_or_create(
            plan=pro_plan,
            product=product,
            defaults={
                'is_included': True,
                'is_addon_available': False,
            }
        )
        if created:
            print(f"   ✅ {product.name} associado ao {pro_plan.name}")
    
    # 6. Associar produtos ao tenant
    print("\n🏢 Associando produtos ao tenant...")
    
    for product in [flow_product, notifications_product]:
        tenant_product, created = TenantProduct.objects.get_or_create(
            tenant=tenant,
            product=product,
            defaults={
                'is_active': True,
                'is_addon': False,
            }
        )
        if created:
            print(f"   ✅ {product.name} associado ao tenant {tenant.name}")
    
    # 7. Criar dados de teste
    print("\n📊 Criando dados de teste...")
    
    # Tags
    tag, created = Tag.objects.get_or_create(
        name="Teste",
        tenant=tenant,
        defaults={'description': 'Tag para testes'}
    )
    if created:
        print(f"   ✅ Tag criada: {tag.name}")
    
    # Lista
    lista, created = List.objects.get_or_create(
        name="Lista Teste",
        tenant=tenant,
        defaults={'description': 'Lista para testes'}
    )
    if created:
        print(f"   ✅ Lista criada: {lista.name}")
    
    # Contatos de teste
    contacts_data = [
        {
            'name': 'João Silva',
            'phone': '+5511999999999',
            'email': 'joao@teste.com',
            'tenant': tenant,
        },
        {
            'name': 'Maria Santos',
            'phone': '+5511888888888',
            'email': 'maria@teste.com',
            'tenant': tenant,
        },
        {
            'name': 'Pedro Costa',
            'phone': '+5511777777777',
            'email': 'pedro@teste.com',
            'tenant': tenant,
        },
    ]
    
    for contact_data in contacts_data:
        contact, created = Contact.objects.get_or_create(
            phone=contact_data['phone'],
            tenant=tenant,
            defaults=contact_data
        )
        if created:
            contact.tags.add(tag)
            contact.lists.add(lista)
            print(f"   ✅ Contato criado: {contact.name}")
    
    # 8. Criar instância WhatsApp de teste
    print("\n📱 Criando instância WhatsApp de teste...")
    
    instance, created = WhatsAppInstance.objects.get_or_create(
        friendly_name="Teste Local",
        tenant=tenant,
        defaults={
            'phone_number': '+5511999999999',
            'connection_state': 'open',
            'is_default': True,
            'is_active': True,
        }
    )
    if created:
        print(f"   ✅ Instância criada: {instance.friendly_name}")
    
    # 9. Criar conexão Evolution de teste
    print("\n🔗 Criando conexão Evolution de teste...")
    
    connection, created = EvolutionConnection.objects.get_or_create(
        name="Teste Local",
        tenant=tenant,
        defaults={
            'base_url': 'http://localhost:8080',
            'api_key': 'test-key',
            'webhook_url': 'http://localhost:8000/api/webhooks/evolution/',
            'is_active': True,
        }
    )
    if created:
        print(f"   ✅ Conexão criada: {connection.name}")
    
    print("\n" + "="*80)
    print("🎉 BANCO LOCAL CONFIGURADO COM SUCESSO!")
    print("="*80)
    print("📋 DADOS DE TESTE CRIADOS:")
    print(f"   • Tenant: {tenant.name}")
    print(f"   • Usuário: admin@teste.local (senha: admin123)")
    print(f"   • Planos: Teste Básico, Teste Pro")
    print(f"   • Produtos: Flow, Notificações")
    print(f"   • Contatos: 3 contatos de teste")
    print(f"   • Tags: Teste")
    print(f"   • Listas: Lista Teste")
    print(f"   • Instância WhatsApp: Teste Local")
    print(f"   • Conexão Evolution: Teste Local")
    print()
    print("🧪 PRÓXIMOS PASSOS:")
    print("   1. Acesse: http://localhost:80")
    print("   2. Login: admin@teste.local / admin123")
    print("   3. Teste o sistema de notificações")
    print("   4. Verifique se o menu aparece")

if __name__ == '__main__':
    create_test_data()
