"""
Script para testar envio de presença (status digitando) via Evolution API
Executa teste direto sem precisar de login
"""
import os
import django
import sys
import requests
import json

# Configurar Django
sys.path.append('backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from django.contrib.auth import get_user_model

User = get_user_model()


def test_send_presence():
    """Testa envio de presença para um número"""
    
    print("="*80)
    print("🧪 TESTE DE ENVIO DE PRESENÇA (STATUS DIGITANDO)")
    print("="*80)
    
    try:
        # Buscar usuário paulo.bernal
        user = User.objects.get(email='paulo.bernal@rbtec.com.br')
        print(f"✅ Usuário: {user.email}")
        print(f"✅ Tenant: {user.tenant.name}")
        
        # Buscar instância ativa
        instance = WhatsAppInstance.objects.filter(
            tenant=user.tenant,
            is_active=True
        ).first()
        
        if not instance:
            print("❌ Nenhuma instância ativa encontrada!")
            return
        
        print(f"✅ Instância: {instance.friendly_name}")
        print(f"   - Instance Name: {instance.instance_name}")
        print(f"   - API URL: {instance.api_url}")
        print(f"   - Status: {instance.status}")
        
        # Configurar teste
        phone = input("\n📱 Digite o número de telefone (com código país, ex: +5517999999999): ").strip()
        if not phone:
            phone = "+5517991253112"  # Número padrão
            print(f"   Usando número padrão: {phone}")
        
        typing_seconds = 3.5
        
        # Preparar dados
        presence_url = f"{instance.api_url}/chat/sendPresence/{instance.instance_name}"
        # 🔧 CORREÇÃO: Evolution API espera delay e presence direto no root
        presence_data = {
            "number": phone,
            "delay": int(typing_seconds * 1000),  # Milissegundos
            "presence": "composing"
        }
        headers = {
            "Content-Type": "application/json",
            "apikey": instance.api_key
        }
        
        print("\n" + "="*80)
        print("📤 REQUEST QUE SERÁ ENVIADO:")
        print("="*80)
        print(f"URL: {presence_url}")
        print(f"Method: POST")
        print(f"\nHeaders:")
        print(f"  Content-Type: {headers['Content-Type']}")
        print(f"  apikey: {'*' * (len(instance.api_key) - 4)}{instance.api_key[-4:]}")
        print(f"\nBody:")
        print(json.dumps(presence_data, indent=2))
        
        # Confirmar
        confirm = input("\n⚠️  Deseja enviar este request? (S/n): ").strip().lower()
        if confirm and confirm != 's':
            print("❌ Teste cancelado")
            return
        
        # Enviar request
        print("\n🚀 Enviando request...")
        response = requests.post(
            presence_url,
            json=presence_data,
            headers=headers,
            timeout=10
        )
        
        # Mostrar response
        print("\n" + "="*80)
        print("📥 RESPONSE RECEBIDO:")
        print("="*80)
        print(f"Status Code: {response.status_code}")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text)
        
        print("\n" + "="*80)
        if response.status_code in [200, 201]:
            print("✅ REQUEST ENVIADO COM SUCESSO!")
            print("📱 Verifique no WhatsApp se apareceu 'digitando...'")
        else:
            print("❌ REQUEST FALHOU!")
            print(f"   Status Code: {response.status_code}")
        print("="*80)
        
    except User.DoesNotExist:
        print("❌ Usuário paulo.bernal@rbtec.com.br não encontrado!")
    except Exception as e:
        print(f"❌ Erro ao testar presença: {e}")
        import traceback
        print("\nTraceback completo:")
        traceback.print_exc()


if __name__ == '__main__':
    test_send_presence()

