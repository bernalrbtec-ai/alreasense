#!/usr/bin/env python3
"""
Script para testar o sistema de limites de instâncias
"""

import requests
import json

# Configurações
BASE_URL = "http://localhost:8000"
LOGIN_EMAIL = "admin@alreasense.com"
LOGIN_PASSWORD = "admin123"

def login():
    """Fazer login e obter token"""
    print("🔐 Fazendo login...")
    
    response = requests.post(f"{BASE_URL}/api/auth/login/", json={
        'email': LOGIN_EMAIL,
        'password': LOGIN_PASSWORD
    })
    
    if response.status_code == 200:
        data = response.json()
        token = data['access']
        print(f"✅ Login realizado com sucesso!")
        return token
    else:
        print(f"❌ Erro no login: {response.status_code} - {response.text}")
        return None

def get_tenant_limits(token):
    """Buscar limites do tenant"""
    print("\n📊 Buscando limites do tenant...")
    
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{BASE_URL}/api/tenants/tenants/limits/", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Limites obtidos com sucesso!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    else:
        print(f"❌ Erro ao buscar limites: {response.status_code} - {response.text}")
        return None

def check_instance_limit(token):
    """Verificar se pode criar instância"""
    print("\n🔍 Verificando limite de instâncias...")
    
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.post(f"{BASE_URL}/api/tenants/tenants/check_instance_limit/", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Verificação de limite realizada!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    else:
        print(f"❌ Erro ao verificar limite: {response.status_code} - {response.text}")
        return None

def get_instances(token):
    """Buscar instâncias existentes"""
    print("\n📱 Buscando instâncias existentes...")
    
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{BASE_URL}/notifications/whatsapp-instances/", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        instances = data.get('results', data) if isinstance(data, dict) else data
        print(f"✅ Encontradas {len(instances)} instâncias:")
        for instance in instances:
            print(f"  - {instance['friendly_name']} ({instance['status']})")
        return instances
    else:
        print(f"❌ Erro ao buscar instâncias: {response.status_code} - {response.text}")
        return []

def create_instance(token, name):
    """Tentar criar uma nova instância"""
    print(f"\n➕ Tentando criar instância '{name}'...")
    
    headers = {'Authorization': f'Bearer {token}'}
    data = {
        'friendly_name': name,
        'is_default': False
    }
    
    response = requests.post(f"{BASE_URL}/notifications/whatsapp-instances/", 
                           headers=headers, json=data)
    
    if response.status_code == 201:
        print(f"✅ Instância '{name}' criada com sucesso!")
        return response.json()
    else:
        print(f"❌ Erro ao criar instância: {response.status_code} - {response.text}")
        return None

def main():
    print("🚀 Testando sistema de limites de instâncias\n")
    
    # Login
    token = login()
    if not token:
        return
    
    # Buscar limites
    limits = get_tenant_limits(token)
    if not limits:
        return
    
    # Verificar limite
    limit_check = check_instance_limit(token)
    if not limit_check:
        return
    
    # Buscar instâncias existentes
    instances = get_instances(token)
    
    # Tentar criar nova instância
    if limit_check.get('can_create', False):
        new_instance = create_instance(token, f"Teste Limite {len(instances) + 1}")
        if new_instance:
            print(f"✅ Teste de criação bem-sucedido!")
    else:
        print(f"⚠️  Não é possível criar nova instância: {limit_check.get('message', 'Limite atingido')}")
    
    print("\n🎉 Teste concluído!")

if __name__ == "__main__":
    main()
