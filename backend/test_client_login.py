"""
Testar login do cliente especificamente
"""

import requests
import json

BASE_URL = 'http://localhost:8000'

print("\n" + "="*60)
print("🔍 TESTE DE LOGIN DO CLIENTE")
print("="*60)

# Teste paulo@rbtec.com
print("\n📧 Email: paulo@rbtec.com")
print("🔐 Senha: senha123")

try:
    response = requests.post(
        f'{BASE_URL}/api/auth/login/',
        json={
            'email': 'paulo@rbtec.com',
            'password': 'senha123'
        },
        headers={'Content-Type': 'application/json'}
    )
    
    print(f"\n📊 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ LOGIN BEM-SUCEDIDO!")
        print(f"\n🔑 Tokens recebidos:")
        print(f"   Access: {data.get('access', '')[:80]}...")
        print(f"   Refresh: {data.get('refresh', '')[:80]}...")
        
        if 'user' in data:
            user = data['user']
            print(f"\n👤 Dados do usuário:")
            print(f"   Email: {user.get('email')}")
            print(f"   Nome: {user.get('first_name')} {user.get('last_name')}")
            print(f"   Role: {user.get('role')}")
            print(f"   Tenant: {user.get('tenant', {}).get('name')}")
            
        # Testar acesso com o token
        print(f"\n🧪 Testando acesso com token...")
        me_response = requests.get(
            f'{BASE_URL}/api/auth/me/',
            headers={
                'Authorization': f'Bearer {data.get("access")}',
                'Content-Type': 'application/json'
            }
        )
        
        if me_response.status_code == 200:
            print(f"✅ Token válido! Usuário autenticado.")
            me_data = me_response.json()
            print(f"   Email: {me_data.get('email')}")
        else:
            print(f"❌ Token inválido ou expirado")
            print(f"   Status: {me_response.status_code}")
            
    else:
        print(f"❌ LOGIN FALHOU")
        print(f"\n📝 Resposta completa:")
        try:
            error_data = response.json()
            print(f"   {json.dumps(error_data, indent=2)}")
        except:
            print(f"   {response.text}")
        
except Exception as e:
    print(f"❌ Erro na requisição: {e}")

print("\n" + "="*60 + "\n")


