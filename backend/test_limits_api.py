#!/usr/bin/env python
"""
Testa o endpoint /tenants/tenants/limits/ para o usuário paulo.bernal@rbtec.com.br
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

# 2. Buscar limites
print(f"\n📊 Buscando limites do tenant...")
headers = {
    'Authorization': f'Bearer {token}'
}

limits_response = requests.get(
    f'{BASE_URL}/api/tenants/tenants/limits/',
    headers=headers
)

print(f"\n📊 Status: {limits_response.status_code}")
print(f"\n📄 Response:")
print(json.dumps(limits_response.json(), indent=2, ensure_ascii=False))

if limits_response.status_code == 200:
    limits = limits_response.json()
    flow_info = limits.get('products', {}).get('flow', {})
    print(f"\n✅ Informações do Flow:")
    print(f"   has_access: {flow_info.get('has_access')}")
    print(f"   current: {flow_info.get('current')}")
    print(f"   limit: {flow_info.get('limit')}")
    print(f"   can_create: {flow_info.get('can_create')}")
    print(f"   message: {flow_info.get('message')}")

