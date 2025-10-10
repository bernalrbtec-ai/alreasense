#!/usr/bin/env python
"""Teste de listagem de instâncias"""
import requests
import json

# Login
response = requests.post(
    'http://localhost:8000/api/auth/login/',
    json={'email': 'admin@alreasense.com', 'password': 'admin123'}
)

token = response.json()['access']
print(f"✅ Logado com sucesso\n")

# Listar instâncias
response = requests.get(
    'http://localhost:8000/api/notifications/whatsapp-instances/',
    headers={'Authorization': f'Bearer {token}'}
)

print(f"Status: {response.status_code}")
print(f"Response:\n")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

# Contar
data = response.json()
if isinstance(data, list):
    print(f"\n✅ Total de instâncias retornadas: {len(data)}")
    for inst in data:
        print(f"  - {inst['friendly_name']} ({inst['connection_state']})")
else:
    print(f"\n⚠️ Resposta não é uma lista: {type(data)}")

