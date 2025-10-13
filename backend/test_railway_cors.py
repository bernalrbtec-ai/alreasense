#!/usr/bin/env python
"""
Teste específico para simular o problema CORS do Railway
"""

import requests
import json

def test_railway_cors():
    """Testa CORS diretamente no Railway"""
    print("🧪 TESTANDO CORS NO RAILWAY...")
    
    base_url = "https://alreasense-backend-production.up.railway.app"
    origin = "https://alreasense-production.up.railway.app"
    
    # Headers que o frontend está enviando
    headers = {
        'Origin': origin,
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Teste 1: OPTIONS request para /api/contacts/tags/
    print(f"\n🔍 Testando OPTIONS {base_url}/api/contacts/tags/")
    try:
        response = requests.options(
            f"{base_url}/api/contacts/tags/",
            headers={
                **headers,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type,authorization'
            }
        )
        print(f"Status: {response.status_code}")
        print(f"CORS Headers:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")
                
        if response.status_code == 200:
            print("✅ OPTIONS request funcionou!")
        else:
            print(f"❌ OPTIONS request falhou: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro no OPTIONS request: {str(e)}")
    
    # Teste 2: POST request para /api/contacts/tags/ (sem auth)
    print(f"\n🔍 Testando POST {base_url}/api/contacts/tags/ (sem auth)")
    try:
        response = requests.post(
            f"{base_url}/api/contacts/tags/",
            headers=headers,
            json={'name': 'Test Tag', 'color': '#FF0000'},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        
        # Verificar se tem CORS headers na resposta
        cors_headers = {k: v for k, v in response.headers.items() if 'access-control' in k.lower()}
        if cors_headers:
            print(f"CORS Headers na resposta:")
            for header, value in cors_headers.items():
                print(f"  {header}: {value}")
        else:
            print("❌ Nenhum header CORS na resposta!")
            
        if response.status_code in [200, 201, 401]:  # 401 é esperado sem auth
            print("✅ POST request funcionou (CORS OK)!")
        else:
            print(f"❌ POST request falhou: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Erro no POST request: {str(e)}")

if __name__ == '__main__':
    test_railway_cors()
