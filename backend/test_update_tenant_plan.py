"""
Script para testar a atualização de plano do tenant
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def login_superadmin():
    """Login como superadmin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login/",
        json={
            "email": "superadmin@alreasense.com",
            "password": "admin123"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Login realizado: {data['user']['email']}")
        return data['access']
    else:
        print(f"❌ Erro no login: {response.status_code}")
        print(response.text)
        return None

def list_tenants(token):
    """Listar tenants"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/tenants/tenants/",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        tenants = data.get('results', data)
        print(f"\n📋 Tenants encontrados: {len(tenants)}")
        for tenant in tenants:
            plan_info = tenant.get('plan_name', 'Sem plano')
            print(f"   - {tenant['name']}: {plan_info} (ID: {tenant['id']})")
        return tenants
    else:
        print(f"❌ Erro ao listar tenants: {response.status_code}")
        return []

def list_plans(token):
    """Listar planos disponíveis"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/billing/plans/",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        plans = data.get('results', data)
        print(f"\n📦 Planos disponíveis: {len(plans)}")
        for plan in plans:
            print(f"   - {plan['name']} ({plan['slug']}): R$ {plan['price']}")
        return plans
    else:
        print(f"❌ Erro ao listar planos: {response.status_code}")
        return []

def update_tenant_plan(token, tenant_id, new_plan_slug):
    """Atualizar plano do tenant"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n🔄 Atualizando tenant {tenant_id} para plano '{new_plan_slug}'...")
    
    response = requests.patch(
        f"{BASE_URL}/api/tenants/tenants/{tenant_id}/",
        headers=headers,
        json={"plan": new_plan_slug}
    )
    
    if response.status_code == 200:
        tenant = response.json()
        print(f"✅ Tenant atualizado com sucesso!")
        print(f"   Novo plano: {tenant.get('plan_name', 'N/A')}")
        print(f"   Produtos ativos: {len(tenant.get('active_products', []))}")
        for product in tenant.get('active_products', []):
            print(f"      - {product['name']}")
        return True
    else:
        print(f"❌ Erro ao atualizar: {response.status_code}")
        print(response.text)
        return False

def get_tenant_details(token, tenant_id):
    """Obter detalhes do tenant"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/tenants/tenants/{tenant_id}/",
        headers=headers
    )
    
    if response.status_code == 200:
        tenant = response.json()
        print(f"\n📊 Detalhes do Tenant:")
        print(f"   Nome: {tenant['name']}")
        print(f"   Plano: {tenant.get('plan_name', 'Sem plano')}")
        print(f"   Produtos ativos: {len(tenant.get('active_products', []))}")
        for product in tenant.get('active_products', []):
            print(f"      - {product['name']}")
        return tenant
    else:
        print(f"❌ Erro ao obter detalhes: {response.status_code}")
        return None

def run_test():
    """Executar teste completo"""
    print("🚀 Teste de Atualização de Plano do Tenant")
    print("=" * 60)
    
    # 1. Login
    token = login_superadmin()
    if not token:
        return
    
    # 2. Listar tenants
    tenants = list_tenants(token)
    if not tenants:
        print("⚠️  Nenhum tenant encontrado")
        return
    
    # 3. Listar planos
    plans = list_plans(token)
    if len(plans) < 2:
        print("⚠️  Menos de 2 planos disponíveis, teste limitado")
    
    # 4. Selecionar primeiro tenant (que não seja Admin)
    test_tenant = None
    for tenant in tenants:
        if 'Admin' not in tenant['name']:
            test_tenant = tenant
            break
    
    if not test_tenant:
        print("⚠️  Nenhum tenant de teste encontrado (pulando Admin)")
        test_tenant = tenants[0]
    
    print(f"\n🎯 Tenant selecionado para teste: {test_tenant['name']}")
    
    # 5. Ver detalhes antes
    print("\n--- ANTES DA ATUALIZAÇÃO ---")
    get_tenant_details(token, test_tenant['id'])
    
    # 6. Trocar para outro plano
    current_plan = test_tenant.get('plan_slug', 'starter')
    
    # Selecionar plano diferente
    new_plan = None
    for plan in plans:
        if plan['slug'] != current_plan:
            new_plan = plan
            break
    
    if not new_plan:
        print("⚠️  Nenhum plano diferente disponível")
        return
    
    # 7. Atualizar plano
    success = update_tenant_plan(token, test_tenant['id'], new_plan['slug'])
    
    if success:
        # 8. Verificar se mudou
        print("\n--- DEPOIS DA ATUALIZAÇÃO ---")
        updated = get_tenant_details(token, test_tenant['id'])
        
        if updated and updated.get('plan_slug') == new_plan['slug']:
            print("\n✅ TESTE PASSOU! Plano foi atualizado corretamente")
        else:
            print("\n❌ TESTE FALHOU! Plano não foi atualizado")
    else:
        print("\n❌ TESTE FALHOU! Erro ao atualizar plano")

if __name__ == '__main__':
    run_test()


