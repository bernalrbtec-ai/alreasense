"""
Script para testar e buscar foto de perfil via Evolution API.
"""
import os
import sys
import django
import httpx
import asyncio
from pathlib import Path

# Setup Django
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.chat.models import Conversation
from apps.tenancy.models import Tenant


async def fetch_profile_pic(instance: EvolutionConnection, phone: str):
    """
    Busca foto de perfil de um contato via Evolution API.
    
    Endpoints possíveis:
    - GET /chat/fetchProfilePictureUrl/{instance}?number={phone}
    - GET /profile/profilePicture/{instance}?number={phone}
    """
    base_url = instance.base_url.rstrip('/')
    headers = {
        'apikey': instance.api_key,
        'Content-Type': 'application/json'
    }
    
    # Formatar número (sem + e sem @s.whatsapp.net)
    clean_phone = phone.replace('+', '')
    
    print(f"\n🔍 Buscando foto de perfil para: {phone}")
    print(f"   Instância: {instance.name}")
    print(f"   Base URL: {base_url}")
    
    # Tentar diferentes endpoints
    endpoints = [
        f"{base_url}/chat/fetchProfilePictureUrl/{instance.name}",
        f"{base_url}/profile/profilePicture/{instance.name}",
        f"{base_url}/contact/profilePicture/{instance.name}"
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in endpoints:
            try:
                print(f"\n📡 Tentando: {endpoint}")
                
                # Método 1: Query param
                response = await client.get(
                    endpoint,
                    params={'number': clean_phone},
                    headers=headers
                )
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Resposta: {data}")
                    
                    # Tentar extrair URL
                    profile_url = (
                        data.get('profilePictureUrl') or
                        data.get('profilePicUrl') or
                        data.get('url') or
                        data.get('picture')
                    )
                    
                    if profile_url:
                        print(f"\n🎉 FOTO ENCONTRADA!")
                        print(f"   URL: {profile_url}")
                        return profile_url
                    else:
                        print(f"   ⚠️ Resposta não contém URL de foto")
                else:
                    print(f"   ❌ Erro: {response.text[:200]}")
                    
            except Exception as e:
                print(f"   ❌ Exceção: {e}")
                continue
    
    print(f"\n❌ Nenhum endpoint retornou foto de perfil")
    return None


async def test_webhook_payload():
    """
    Verifica se o webhook está recebendo profilePicUrl.
    """
    print("\n" + "="*60)
    print("📋 VERIFICANDO PAYLOAD DO WEBHOOK")
    print("="*60)
    
    # Buscar última conversa
    last_conv = Conversation.objects.order_by('-created_at').first()
    
    if not last_conv:
        print("❌ Nenhuma conversa encontrada no banco")
        return
    
    print(f"\n📞 Última conversa:")
    print(f"   Contato: {last_conv.contact_name or last_conv.contact_phone}")
    print(f"   Telefone: {last_conv.contact_phone}")
    print(f"   Foto de Perfil: {last_conv.profile_pic_url or 'NÃO TEM'}")
    
    if last_conv.profile_pic_url:
        print(f"\n✅ URL salva no banco:")
        print(f"   {last_conv.profile_pic_url}")
        
        # Testar se URL está acessível
        print(f"\n🔍 Testando se URL está acessível...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.head(last_conv.profile_pic_url)
                if response.status_code == 200:
                    print(f"   ✅ URL válida! Status: {response.status_code}")
                    print(f"   Content-Type: {response.headers.get('content-type')}")
                else:
                    print(f"   ❌ URL inválida! Status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Erro ao acessar URL: {e}")
    else:
        print(f"\n⚠️ Foto de perfil NÃO foi salva no banco")
        print(f"   Possíveis causas:")
        print(f"   1. Evolution não enviou 'profilePicUrl' no webhook")
        print(f"   2. Campo está vindo com nome diferente")
        print(f"   3. Contato não tem foto de perfil no WhatsApp")


async def main():
    """Menu principal."""
    print("\n" + "="*60)
    print("🔬 DIAGNÓSTICO - FOTO DE PERFIL NO CHAT")
    print("="*60)
    
    # Testar payload do webhook primeiro
    await test_webhook_payload()
    
    # Buscar instância ativa
    instance = EvolutionConnection.objects.filter(is_active=True).first()
    
    if not instance:
        print("\n❌ Nenhuma instância Evolution ativa encontrada")
        return
    
    print(f"\n" + "="*60)
    print(f"📡 BUSCANDO FOTO VIA API EVOLUTION")
    print(f"="*60)
    
    # Pedir número para testar
    phone = input("\n📞 Digite o telefone para buscar foto (ex: +5517999999999): ").strip()
    
    if not phone:
        print("❌ Telefone não fornecido")
        return
    
    profile_url = await fetch_profile_pic(instance, phone)
    
    if profile_url:
        # Atualizar no banco
        try:
            conv = Conversation.objects.get(
                tenant=instance.tenant,
                contact_phone=phone
            )
            conv.profile_pic_url = profile_url
            conv.save(update_fields=['profile_pic_url'])
            print(f"\n✅ Foto atualizada no banco para conversa: {conv.id}")
        except Conversation.DoesNotExist:
            print(f"\n⚠️ Conversa não existe no banco para este telefone")


if __name__ == '__main__':
    asyncio.run(main())


