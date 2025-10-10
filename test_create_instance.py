#!/usr/bin/env python
"""Teste de criação de instância WhatsApp"""
import requests

# 1. Login
print("1️⃣ Fazendo login...")
response = requests.post(
    'http://localhost:8000/api/auth/login/',
    json={
        'email': 'admin@alreasense.com',
        'password': 'admin123'
    }
)
print(f"   Status: {response.status_code}")

if response.status_code != 200:
    print(f"   ❌ Erro no login: {response.text}")
    exit(1)

token = response.json()['access']
print(f"   ✅ Token obtido: {token[:30]}...")

# 2. Criar instância
print("\n2️⃣ Criando instância WhatsApp...")
response = requests.post(
    'http://localhost:8000/api/notifications/whatsapp-instances/',
    json={
        'friendly_name': 'Teste Python',
        'is_default': False
    },
    headers={'Authorization': f'Bearer {token}'}
)

print(f"   Status: {response.status_code}")
print(f"   Response: {response.text[:500]}")

if response.status_code == 201:
    print(f"\n   ✅ Instância criada com sucesso!")
    print(f"   ID: {response.json()['id']}")
else:
    print(f"\n   ❌ Erro ao criar instância!")
    print(f"   Detalhes: {response.json()}")

