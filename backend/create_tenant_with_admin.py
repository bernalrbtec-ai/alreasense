#!/usr/bin/env python3
"""
Script para criar tenant com usuário admin
O admin É o próprio tenant (não há separação)
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.billing.models import Plan, PlanProduct, TenantProduct

User = get_user_model()


def create_tenant_with_admin(
    tenant_name,
    admin_email,
    admin_password,
    plan_slug='starter',
    admin_first_name='',
    admin_last_name=''
):
    """
    Cria um tenant completo com usuário admin.
    
    Args:
        tenant_name: Nome do tenant/empresa
        admin_email: Email do usuário admin
        admin_password: Senha do admin
        plan_slug: Slug do plano (starter, pro, api_only, enterprise)
        admin_first_name: Nome do admin
        admin_last_name: Sobrenome do admin
    """
    
    print(f"\n🚀 Criando tenant: {tenant_name}")
    print(f"📧 Admin: {admin_email}")
    print(f"💰 Plano: {plan_slug}")
    print("=" * 50)
    
    # 1. Buscar plano
    try:
        plan = Plan.objects.get(slug=plan_slug, is_active=True)
        print(f"✅ Plano encontrado: {plan.name} (R$ {plan.price}/mês)")
    except Plan.DoesNotExist:
        print(f"❌ Plano '{plan_slug}' não encontrado")
        print(f"   Planos disponíveis: {', '.join(Plan.objects.filter(is_active=True).values_list('slug', flat=True))}")
        return None
    
    # 2. Criar tenant
    tenant, created = Tenant.objects.get_or_create(
        name=tenant_name,
        defaults={
            'current_plan': plan,
            'status': 'active',
            'ui_access': True
        }
    )
    
    if created:
        print(f"✅ Tenant criado: {tenant.name}")
    else:
        print(f"⚠️  Tenant já existe: {tenant.name}")
        tenant.current_plan = plan
        tenant.save()
        print(f"   Plano atualizado para: {plan.name}")
    
    # 3. Ativar produtos do plano
    print(f"\n📦 Ativando produtos do plano {plan.name}...")
    
    # Buscar produtos incluídos no plano
    plan_products = PlanProduct.objects.filter(
        plan=plan,
        is_included=True
    ).select_related('product')
    
    activated_count = 0
    for plan_product in plan_products:
        tenant_product, created = TenantProduct.objects.get_or_create(
            tenant=tenant,
            product=plan_product.product,
            defaults={
                'is_addon': False,
                'is_active': True,
                'addon_price': None
            }
        )
        
        if created:
            print(f"   ✅ {plan_product.product.name} ativado")
            activated_count += 1
        else:
            if not tenant_product.is_active:
                tenant_product.is_active = True
                tenant_product.save()
                print(f"   ✅ {plan_product.product.name} reativado")
                activated_count += 1
            else:
                print(f"   ℹ️  {plan_product.product.name} já estava ativo")
    
    print(f"\n✅ {activated_count} produtos ativados")
    
    # 4. Criar usuário admin
    print(f"\n👤 Criando usuário admin...")
    
    user, created = User.objects.get_or_create(
        email=admin_email,
        defaults={
            'username': admin_email.split('@')[0],  # Usar parte do email como username
            'first_name': admin_first_name or 'Admin',
            'last_name': admin_last_name or tenant_name,
            'is_superuser': False,  # NÃO é admin da aplicação
            'is_staff': False,      # NÃO tem acesso ao Django Admin
            'is_active': True,
            'tenant': tenant,       # Vinculado ao tenant/cliente
            'role': 'admin'         # Admin do CLIENTE (não da aplicação)
        }
    )
    
    if created:
        user.set_password(admin_password)
        user.save()
        print(f"✅ Usuário admin criado: {user.email}")
    else:
        print(f"⚠️  Usuário já existe: {user.email}")
        # Atualizar tenant e senha
        user.tenant = tenant
        user.set_password(admin_password)
        user.role = 'admin'
        user.save()
        print(f"   Usuário atualizado e vinculado ao tenant")
    
    # 5. Resumo
    print(f"\n{'='*50}")
    print(f"🎉 TENANT CRIADO COM SUCESSO!")
    print(f"{'='*50}")
    print(f"\n📋 INFORMAÇÕES DE ACESSO:")
    print(f"   🏢 Tenant: {tenant.name}")
    print(f"   📧 Email: {user.email}")
    print(f"   🔑 Senha: {admin_password}")
    print(f"   💰 Plano: {plan.name} (R$ {plan.price}/mês)")
    print(f"\n📦 PRODUTOS ATIVOS:")
    
    for tp in tenant.active_products:
        limit_info = ""
        if tp.product.slug == 'flow':
            limit_info = f" ({tenant.get_instance_limit_info()['message']})"
        print(f"   ✅ {tp.product.name}{limit_info}")
    
    print(f"\n💵 Total mensal: R$ {tenant.monthly_total}")
    print(f"\n🌐 Acesse: http://localhost")
    print(f"\n{'='*50}\n")
    
    return tenant, user


def main():
    """Criar tenant de exemplo"""
    
    print("\n" + "="*50)
    print("🏢 CRIAÇÃO DE TENANT COM ADMIN")
    print("="*50)
    
    # Exemplo: Criar tenant Admin com plano Starter
    tenant, user = create_tenant_with_admin(
        tenant_name='Admin Tenant',
        admin_email='admin@alreasense.com',
        admin_password='admin123',
        plan_slug='starter',
        admin_first_name='Admin',
        admin_last_name='System'
    )
    
    if tenant and user:
        print("✅ Setup completo!")
    else:
        print("❌ Erro na criação do tenant")


if __name__ == "__main__":
    main()

