#!/usr/bin/env python
"""
Script para testar CORS
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

def test_cors():
    """Testa CORS para diferentes endpoints"""
    print("🧪 TESTANDO CORS...")
    
    client = Client()
    
    # Testar endpoint de tags com OPTIONS
    print("\n🔍 Testando OPTIONS /api/contacts/tags/")
    response = client.options(
        '/api/contacts/tags/',
        HTTP_ORIGIN='https://alreasense-production.up.railway.app',
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type,authorization'
    )
    
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.items())}")
    
    # Testar endpoint de tags com POST (sem autenticação)
    print("\n🔍 Testando POST /api/contacts/tags/")
    response = client.post(
        '/api/contacts/tags/',
        {'name': 'Test Tag', 'color': '#FF0000'},
        content_type='application/json',
        HTTP_ORIGIN='https://alreasense-production.up.railway.app'
    )
    
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.items())}")
    
    # Testar endpoint de preview CSV
    print("\n🔍 Testando OPTIONS /api/contacts/contacts/preview_csv/")
    response = client.options(
        '/api/contacts/contacts/preview_csv/',
        HTTP_ORIGIN='https://alreasense-production.up.railway.app'
    )
    
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.items())}")

if __name__ == '__main__':
    test_cors()
