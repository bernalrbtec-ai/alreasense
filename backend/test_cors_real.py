#!/usr/bin/env python
"""Teste CORS com requisição POST real"""
import requests

BASE_URL = 'http://localhost:8000'

print("\n🧪 Teste CORS - Requisição POST Real")

# Fazer uma requisição real como o browser faria
response = requests.post(
    f'{BASE_URL}/api/auth/login/',
    headers={
        'Origin': 'http://localhost',
        'Content-Type': 'application/json'
    },
    json={
        'email': 'teste@campanhas.com',
        'password': 'teste123'
    }
)

print(f"\nStatus: {response.status_code}")
print(f"\nHeaders CORS na resposta:")
print(f"   Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
print(f"   Access-Control-Allow-Credentials: {response.headers.get('Access-Control-Allow-Credentials')}")

if response.headers.get('Access-Control-Allow-Origin'):
    print(f"\n✅ CORS está funcionando corretamente!")
    print(f"   Frontend ({response.headers.get('Access-Control-Allow-Origin')}) pode fazer requisições")
else:
    print(f"\n❌ CORS NÃO está configurado")




