"""
Script para atualizar fotos de perfil de todas as conversas via Evolution API.
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


async def fetch_profile_pic(instance: EvolutionConnection, phone: str) -> str | None:
    """Busca foto de perfil de um contato."""
    base_url = instance.base_url.rstrip('/')
    headers = {
        'apikey': instance.api_key,
        'Content-Type': 'application/json'
    }
    
    clean_phone = phone.replace('+', '')
    
    # Endpoint correto da Evolution API v2
    endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance.name}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                endpoint,
                params={'number': clean_phone},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                profile_url = (
                    data.get('profilePictureUrl') or
                    data.get('profilePicUrl') or
                    data.get('url')
                )
                return profile_url
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    return None


async def update_all_conversations():
    """Atualiza fotos de perfil de todas as conversas."""
    
    # Buscar instância ativa
    instance = EvolutionConnection.objects.filter(is_active=True).first()
    
    if not instance:
        print("❌ Nenhuma instância Evolution ativa")
        return
    
    print(f"\n✅ Usando instância: {instance.name}")
    print(f"   Tenant: {instance.tenant.name}")
    
    # Buscar conversas sem foto ou com foto antiga
    conversations = Conversation.objects.filter(
        tenant=instance.tenant
    ).order_by('-last_message_at')[:50]  # Últimas 50
    
    print(f"\n🔍 Processando {conversations.count()} conversas...")
    
    updated = 0
    failed = 0
    skipped = 0
    
    for conv in conversations:
        phone = conv.contact_phone
        name = conv.contact_name or phone
        
        print(f"\n📞 {name} ({phone})")
        
        # Buscar foto
        profile_url = await fetch_profile_pic(instance, phone)
        
        if profile_url:
            if conv.profile_pic_url != profile_url:
                conv.profile_pic_url = profile_url
                conv.save(update_fields=['profile_pic_url'])
                print(f"   ✅ Foto atualizada!")
                updated += 1
            else:
                print(f"   ⏭️ Foto já está atualizada")
                skipped += 1
        else:
            print(f"   ❌ Foto não encontrada")
            failed += 1
        
        # Delay para não sobrecarregar API
        await asyncio.sleep(0.5)
    
    print(f"\n" + "="*60)
    print(f"📊 RESULTADO:")
    print(f"   ✅ Atualizadas: {updated}")
    print(f"   ⏭️ Já atualizadas: {skipped}")
    print(f"   ❌ Sem foto: {failed}")
    print(f"="*60)


if __name__ == '__main__':
    asyncio.run(update_all_conversations())


