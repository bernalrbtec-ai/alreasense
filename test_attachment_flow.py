#!/usr/bin/env python3
"""
Script de teste para verificar o fluxo completo de anexos.
"""
import requests
import json
import os
from datetime import datetime

# Configurações
API_URL = "https://alreasense-backend-production.up.railway.app"
EMAIL = "paulo.bernal@rbtec.com.br"
PASSWORD = "Paulo@2508"

def test_attachment_flow():
    """Testa fluxo completo de anexos."""
    
    print("🔐 [1/5] Autenticando...")
    login_response = requests.post(
        f"{API_URL}/api/auth/login/",
        json={"email": EMAIL, "password": PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Falha no login: {login_response.status_code}")
        print(login_response.text)
        return
    
    token = login_response.json()["access"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"✅ Token obtido: {token[:20]}...")
    
    # Listar conversas
    print("\n📋 [2/5] Listando conversas...")
    conv_response = requests.get(
        f"{API_URL}/api/chat/conversations/?ordering=-last_message_at&status=pending",
        headers=headers
    )
    
    if conv_response.status_code != 200:
        print(f"❌ Falha ao listar conversas: {conv_response.status_code}")
        return
    
    conversations_data = conv_response.json()
    
    # API pode retornar lista ou objeto com 'results'
    if isinstance(conversations_data, dict):
        conversations = conversations_data.get('results', [])
    else:
        conversations = conversations_data
    
    if not conversations:
        print("❌ Nenhuma conversa encontrada")
        print(f"   Response: {conversations_data}")
        return
    
    conversation_id = conversations[0]["id"]
    print(f"✅ Conversa selecionada: {conversation_id}")
    
    # Obter presigned URL
    print("\n📤 [3/5] Solicitando presigned URL...")
    presigned_response = requests.post(
        f"{API_URL}/api/chat/messages/upload-presigned-url/",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "file_size": 1024
        }
    )
    
    if presigned_response.status_code != 200:
        print(f"❌ Falha ao obter presigned URL: {presigned_response.status_code}")
        print(presigned_response.text)
        return
    
    presigned_data = presigned_response.json()
    print(f"✅ Presigned URL obtida!")
    print(f"   Upload URL: {presigned_data['upload_url'][:80]}...")
    print(f"   Attachment ID: {presigned_data['attachment_id']}")
    print(f"   S3 Key: {presigned_data['s3_key']}")
    
    # Testar upload S3
    print("\n📦 [4/5] Testando upload para S3...")
    test_data = b"Test file content"
    
    s3_response = requests.put(
        presigned_data['upload_url'],
        data=test_data,
        headers={"Content-Type": "application/pdf"}
    )
    
    print(f"   Status Code: {s3_response.status_code}")
    
    if s3_response.status_code not in [200, 204]:
        print(f"❌ Falha no upload S3: {s3_response.status_code}")
        print(f"   Response: {s3_response.text[:200]}")
        return
    
    print(f"✅ Upload S3 bem-sucedido!")
    
    # Confirmar upload
    print("\n✅ [5/5] Confirmando upload no backend...")
    confirm_response = requests.post(
        f"{API_URL}/api/chat/messages/confirm-upload/",
        headers=headers,
        json={
            "conversation_id": conversation_id,
            "attachment_id": presigned_data['attachment_id'],
            "s3_key": presigned_data['s3_key'],
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "file_size": len(test_data)
        }
    )
    
    print(f"   Status Code: {confirm_response.status_code}")
    
    if confirm_response.status_code != 201:
        print(f"❌ Falha no confirm: {confirm_response.status_code}")
        print(f"   Response: {confirm_response.text[:500]}")
        return
    
    confirm_data = confirm_response.json()
    print(f"✅ Upload confirmado!")
    print(f"   Message ID: {confirm_data['message']['id']}")
    print(f"   Attachment ID: {confirm_data['attachment']['id']}")
    
    # Aguardar task RabbitMQ
    print("\n⏳ Aguarde 5 segundos para a task processar...")
    import time
    time.sleep(5)
    
    print("\n" + "="*70)
    print("✅ FLUXO COMPLETO EXECUTADO!")
    print("="*70)
    print("\n📋 Próximos passos:")
    print("1. Verifique os logs do Railway")
    print("2. Procure por: 🔍 [CHAT] Enviando mídia para Evolution API")
    print("3. Verifique se o payload tem 'mediaType' (camelCase)")
    print("4. Verifique se a Evolution API retornou 200 OK")
    print("\n🔍 URL dos logs:")
    print("https://railway.app/dashboard")

if __name__ == "__main__":
    try:
        test_attachment_flow()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

