#!/usr/bin/env python3
"""
Teste direto da Evolution API - sendMedia endpoint.
Baseado na documentação do Postman.
"""
import requests
import json

# Configurações
EVOLUTION_URL = "https://evo.rbtec.com.br"
INSTANCE_NAME = "0cd3505a-c6e5-454d-9f88-e66c41e8761f"
API_KEY = "5A0FAE3A1CB3-4EAA-A79F-D9B10966"  # Pegar do Railway

# URL pública de teste (imagem pequena)
TEST_IMAGE_URL = "https://via.placeholder.com/150"

def test_sendMedia_variations():
    """Testa diferentes variações do payload."""
    
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }
    
    phone = "+5517991253112"
    
    print("="*70)
    print("TESTANDO DIFERENTES PAYLOADS PARA EVOLUTION API")
    print("="*70)
    
    # Teste 1: Estrutura que estamos usando atualmente
    print("\n[TESTE 1] Payload atual do código:")
    payload1 = {
        "number": phone,
        "mediaMessage": {
            "media": TEST_IMAGE_URL,
            "mediaType": "image",
            "fileName": "test.jpg"
        }
    }
    print(json.dumps(payload1, indent=2))
    
    response1 = requests.post(
        f"{EVOLUTION_URL}/message/sendMedia/{INSTANCE_NAME}",
        headers=headers,
        json=payload1
    )
    print(f"Status: {response1.status_code}")
    print(f"Response: {response1.text[:500]}")
    
    # Teste 2: Com 'mediatype' (lowercase)
    print("\n[TESTE 2] Com mediatype (lowercase):")
    payload2 = {
        "number": phone,
        "mediaMessage": {
            "media": TEST_IMAGE_URL,
            "mediatype": "image",  # lowercase
            "fileName": "test.jpg"
        }
    }
    print(json.dumps(payload2, indent=2))
    
    response2 = requests.post(
        f"{EVOLUTION_URL}/message/sendMedia/{INSTANCE_NAME}",
        headers=headers,
        json=payload2
    )
    print(f"Status: {response2.status_code}")
    print(f"Response: {response2.text[:500]}")
    
    # Teste 3: Base64 (alternativa)
    print("\n[TESTE 3] Com base64 (se aplicável):")
    payload3 = {
        "number": phone,
        "options": {
            "delay": 1200,
            "presence": "composing"
        },
        "mediaMessage": {
            "mediatype": "image",
            "media": TEST_IMAGE_URL
        }
    }
    print(json.dumps(payload3, indent=2))
    
    response3 = requests.post(
        f"{EVOLUTION_URL}/message/sendMedia/{INSTANCE_NAME}",
        headers=headers,
        json=payload3
    )
    print(f"Status: {response3.status_code}")
    print(f"Response: {response3.text[:500]}")
    
    # Teste 4: Estrutura simplificada
    print("\n[TESTE 4] Estrutura simplificada:")
    payload4 = {
        "number": phone,
        "media": TEST_IMAGE_URL,
        "mediatype": "image"
    }
    print(json.dumps(payload4, indent=2))
    
    response4 = requests.post(
        f"{EVOLUTION_URL}/message/sendMedia/{INSTANCE_NAME}",
        headers=headers,
        json=payload4
    )
    print(f"Status: {response4.status_code}")
    print(f"Response: {response4.text[:500]}")
    
    print("\n" + "="*70)
    print("RESUMO:")
    print("="*70)
    print(f"Teste 1 (mediaType camelCase): {response1.status_code}")
    print(f"Teste 2 (mediatype lowercase): {response2.status_code}")
    print(f"Teste 3 (com options): {response3.status_code}")
    print(f"Teste 4 (simplificado): {response4.status_code}")
    print("\n✅ Use o payload que retornou 200/201!")

if __name__ == "__main__":
    try:
        test_sendMedia_variations()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()





























