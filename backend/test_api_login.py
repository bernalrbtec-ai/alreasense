"""
Testar login via API HTTP (como o frontend faz)
"""

import requests
import json

BASE_URL = 'http://localhost:8000'

print("\n" + "="*60)
print("🌐 TESTE DE LOGIN VIA API HTTP")
print("="*60)

# Teste 1: Super Admin
print("\n1️⃣ Teste: superadmin@alreasense.com / admin123")
try:
    response = requests.post(
        f'{BASE_URL}/api/auth/login/',
        json={
            'email': 'superadmin@alreasense.com',
            'password': 'admin123'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ SUCESSO!")
        print(f"   🔑 Access Token: {data.get('access', '')[:50]}...")
        print(f"   🔄 Refresh Token: {data.get('refresh', '')[:50]}...")
        if 'user' in data:
            print(f"   👤 User: {data['user'].get('email')}")
    else:
        print(f"   ❌ FALHOU")
        print(f"   Resposta: {response.text}")
        
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Teste 2: Admin do Cliente
print("\n2️⃣ Teste: paulo@rbtec.com / senha123")
try:
    response = requests.post(
        f'{BASE_URL}/api/auth/login/',
        json={
            'email': 'paulo@rbtec.com',
            'password': 'senha123'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ SUCESSO!")
        print(f"   🔑 Access Token: {data.get('access', '')[:50]}...")
        print(f"   🔄 Refresh Token: {data.get('refresh', '')[:50]}...")
        if 'user' in data:
            print(f"   👤 User: {data['user'].get('email')}")
    else:
        print(f"   ❌ FALHOU")
        print(f"   Resposta: {response.text}")
        
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Teste 3: Senha errada
print("\n3️⃣ Teste: paulo@rbtec.com / senhaerrada")
try:
    response = requests.post(
        f'{BASE_URL}/api/auth/login/',
        json={
            'email': 'paulo@rbtec.com',
            'password': 'senhaerrada'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"   ⚠️ ALERTA: Senha errada foi aceita!")
    else:
        print(f"   ✅ Corretamente rejeitado")
        print(f"   Mensagem: {response.json().get('detail', '')}")
        
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n" + "="*60)
print("✅ TESTE COMPLETO!")
print("="*60 + "\n")


