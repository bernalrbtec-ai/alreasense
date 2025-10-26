#!/usr/bin/env python3
"""
Teste REAL com Evolution API usando dados do banco.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

import requests
import json
from apps.notifications.models import WhatsAppInstance

def test_evolution_sendMedia():
    """Testa Evolution API com dados reais do banco."""
    
    print("="*70)
    print("TESTE EVOLUTION API - SendMedia")
    print("="*70)
    
    # Buscar instância ativa
    print("\n1. Buscando instância WhatsApp ativa...")
    instance = WhatsAppInstance.objects.filter(is_active=True).first()
    
    if not instance:
        print("❌ Nenhuma instância ativa encontrada!")
        return
    
    print(f"✅ Instância encontrada:")
    print(f"   Nome: {instance.instance_name}")
    print(f"   API URL: {instance.api_url}")
    print(f"   API Key: {instance.api_key[:20]}...")
    print(f"   Tenant: {instance.tenant.name}")
    
    # Configurar teste
    headers = {
        "apikey": instance.api_key,
        "Content-Type": "application/json"
    }
    
    # URL de imagem pública de teste
    test_image_url = "https://via.placeholder.com/150"
    phone = "+5517991253112"  # Seu número de teste
    
    base_url = instance.api_url.rstrip('/')
    endpoint = f"{base_url}/message/sendMedia/{instance.instance_name}"
    
    print(f"\n2. Testando diferentes estruturas de payload...")
    print(f"   Endpoint: {endpoint}")
    print(f"   Telefone: {phone}")
    
    # TESTE 1: Estrutura atual (mediaType camelCase)
    print("\n[TESTE 1] mediaType (camelCase):")
    payload1 = {
        "number": phone,
        "mediaMessage": {
            "media": test_image_url,
            "mediaType": "image",
            "fileName": "test.jpg"
        }
    }
    print(f"Payload: {json.dumps(payload1, indent=2)}")
    
    response1 = requests.post(endpoint, headers=headers, json=payload1)
    print(f"Status: {response1.status_code}")
    print(f"Body: {response1.text[:300]}")
    
    # TESTE 2: mediatype (lowercase)
    print("\n[TESTE 2] mediatype (lowercase):")
    payload2 = {
        "number": phone,
        "mediaMessage": {
            "media": test_image_url,
            "mediatype": "image",  # lowercase
            "fileName": "test.jpg"
        }
    }
    print(f"Payload: {json.dumps(payload2, indent=2)}")
    
    response2 = requests.post(endpoint, headers=headers, json=payload2)
    print(f"Status: {response2.status_code}")
    print(f"Body: {response2.text[:300]}")
    
    # TESTE 3: Estrutura simplificada (direto no root)
    print("\n[TESTE 3] Estrutura simplificada (sem mediaMessage):")
    payload3 = {
        "number": phone,
        "media": test_image_url,
        "mediatype": "image"
    }
    print(f"Payload: {json.dumps(payload3, indent=2)}")
    
    response3 = requests.post(endpoint, headers=headers, json=payload3)
    print(f"Status: {response3.status_code}")
    print(f"Body: {response3.text[:300]}")
    
    # TESTE 4: Com options (conforme doc Evolution)
    print("\n[TESTE 4] Com options (delay + presence):")
    payload4 = {
        "number": phone,
        "options": {
            "delay": 1200,
            "presence": "composing"
        },
        "mediaMessage": {
            "mediatype": "image",
            "media": test_image_url
        }
    }
    print(f"Payload: {json.dumps(payload4, indent=2)}")
    
    response4 = requests.post(endpoint, headers=headers, json=payload4)
    print(f"Status: {response4.status_code}")
    print(f"Body: {response4.text[:300]}")
    
    # Resumo
    print("\n" + "="*70)
    print("RESUMO DOS TESTES:")
    print("="*70)
    tests = [
        ("Teste 1 (mediaType camelCase)", response1.status_code),
        ("Teste 2 (mediatype lowercase)", response2.status_code),
        ("Teste 3 (simplificado)", response3.status_code),
        ("Teste 4 (com options)", response4.status_code)
    ]
    
    for name, status in tests:
        icon = "✅" if status in [200, 201] else "❌"
        print(f"{icon} {name}: {status}")
    
    # Identificar qual funcionou
    successful = [name for name, status in tests if status in [200, 201]]
    if successful:
        print(f"\n✅ USE O PAYLOAD DO: {successful[0]}")
    else:
        print(f"\n❌ NENHUM TESTE FOI BEM-SUCEDIDO!")
        print(f"   Verifique se a instância WhatsApp está conectada na Evolution API")

if __name__ == "__main__":
    try:
        test_evolution_sendMedia()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()




