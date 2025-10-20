"""
Script para forçar o carregamento de foto de perfil de uma conversa.
"""
import os
import sys
import django
import httpx

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.chat.models import Conversation
from apps.connections.models import EvolutionConnection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.chat.api.serializers import ConversationSerializer


def fetch_profile_pic(conversation_id: str):
    """Busca foto de perfil de uma conversa específica."""
    try:
        # Buscar conversa
        conversation = Conversation.objects.get(id=conversation_id)
        print(f"\n✅ Conversa encontrada:")
        print(f"   ID: {conversation.id}")
        print(f"   Nome: {conversation.contact_name}")
        print(f"   Telefone: {conversation.contact_phone}")
        print(f"   Foto atual: {conversation.profile_pic_url or 'NENHUMA'}")
        
        # Buscar instância Evolution ativa
        instance = EvolutionConnection.objects.filter(
            tenant=conversation.tenant,
            is_active=True
        ).first()
        
        if not instance:
            print("❌ Nenhuma instância Evolution ativa encontrada!")
            return
        
        print(f"\n🔌 Instância Evolution: {instance.name}")
        print(f"   Base URL: {instance.base_url}")
        
        # Formatar telefone (sem + e sem @s.whatsapp.net)
        clean_phone = conversation.contact_phone.replace('+', '').replace('@s.whatsapp.net', '')
        
        # Endpoint Evolution API
        base_url = instance.base_url.rstrip('/')
        endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance.name}"
        
        headers = {
            'apikey': instance.api_key,
            'Content-Type': 'application/json'
        }
        
        print(f"\n📡 Buscando foto de perfil...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Telefone: {clean_phone}")
        
        # Buscar foto
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                endpoint,
                params={'number': clean_phone},
                headers=headers
            )
            
            print(f"\n📥 Resposta HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Dados: {data}")
                
                profile_url = (
                    data.get('profilePictureUrl') or
                    data.get('profilePicUrl') or
                    data.get('url') or
                    data.get('picture')
                )
                
                if profile_url:
                    print(f"\n✅ Foto encontrada!")
                    print(f"   URL: {profile_url[:100]}...")
                    
                    # Salvar no banco
                    conversation.profile_pic_url = profile_url
                    conversation.save(update_fields=['profile_pic_url'])
                    print(f"\n💾 Foto salva no banco de dados!")
                    
                    # Broadcast via WebSocket
                    try:
                        conv_data = ConversationSerializer(conversation).data
                        
                        # Converter UUIDs
                        def convert_uuids(obj):
                            import uuid
                            if isinstance(obj, uuid.UUID):
                                return str(obj)
                            elif isinstance(obj, dict):
                                return {k: convert_uuids(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [convert_uuids(item) for item in obj]
                            return obj
                        
                        conv_data_clean = convert_uuids(conv_data)
                        
                        channel_layer = get_channel_layer()
                        tenant_group = f"chat_tenant_{conversation.tenant_id}"
                        
                        async_to_sync(channel_layer.group_send)(
                            tenant_group,
                            {
                                'type': 'conversation_updated',
                                'conversation': conv_data_clean
                            }
                        )
                        
                        print(f"📡 Atualização broadcast via WebSocket!")
                        print(f"\n✅ CONCLUÍDO! Recarregue o frontend para ver a foto.")
                    except Exception as e:
                        print(f"⚠️ Erro ao fazer broadcast: {e}")
                        print(f"   A foto foi salva, mas talvez precise recarregar a página.")
                else:
                    print(f"\n❌ Foto não encontrada na resposta!")
                    print(f"   Resposta completa: {data}")
            else:
                print(f"❌ Erro na requisição!")
                print(f"   Status: {response.status_code}")
                print(f"   Resposta: {response.text}")
                
    except Conversation.DoesNotExist:
        print(f"❌ Conversa {conversation_id} não encontrada!")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("❌ Uso: python force_fetch_profile_pic.py <conversation_id>")
        print("\n💡 Para encontrar o conversation_id:")
        print("   1. Abra o chat no navegador")
        print("   2. Veja a URL: /chat/<conversation_id>")
        sys.exit(1)
    
    conversation_id = sys.argv[1]
    fetch_profile_pic(conversation_id)

