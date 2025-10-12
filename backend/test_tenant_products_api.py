#!/usr/bin/env python
"""
Testa o endpoint /billing/tenant-products/ para o usuário paulo.bernal@rbtec.com.br
"""
import requests
import json

BASE_URL = 'http://localhost:8000'

# 1. Fazer login
print("\n🔐 Fazendo login...")
login_response = requests.post(
    f'{BASE_URL}/api/auth/login/',
    json={
        'email': 'paulo.bernal@rbtec.com.br',
        'password': 'senha123'
    }
)

if login_response.status_code != 200:
    print(f"❌ Erro no login: {login_response.status_code}")
    print(login_response.text)
    exit(1)

login_data = login_response.json()
token = login_data.get('access')
user = login_data.get('user')

print(f"✅ Login bem-sucedido!")
print(f"   Usuário: {user.get('email')}")
print(f"   Tenant: {user.get('tenant', {}).get('name')}")

# 2. Buscar tenant products
print(f"\n📦 Buscando produtos do tenant...")
headers = {
    'Authorization': f'Bearer {token}'
}

tenant_products_response = requests.get(
    f'{BASE_URL}/api/billing/tenant-products/',
    headers=headers
)

print(f"\n📊 Status: {tenant_products_response.status_code}")
print(f"\n📄 Response:")
print(json.dumps(tenant_products_response.json(), indent=2, ensure_ascii=False))

if tenant_products_response.status_code == 200:
    tenant_products = tenant_products_response.json()
    print(f"\n✅ {len(tenant_products)} produtos encontrados:")
    for tp in tenant_products:
        product = tp.get('product', {})
        print(f"   - {product.get('name')} ({product.get('slug')})")
        print(f"     Ativo: {tp.get('is_active')}")
        print(f"     Add-on: {tp.get('is_addon')}")


