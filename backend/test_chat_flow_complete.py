"""
🧪 TESTE COMPLETO DO FLUXO DE CHAT
Simula o fluxo completo de mensagens para validar antes de fazer mudanças.
"""
import os
import sys
import django
import json

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'apps'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tenancy.models import Tenant
from apps.notifications.models import WhatsAppInstance
from apps.chat.models import Conversation, Message
from apps.chat.webhooks import handle_message_upsert, handle_message_update
from django.utils import timezone

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_incoming_message():
    """Testa recebimento de mensagem (resposta do contato)"""
    print_section("📥 TESTE 1: MENSAGEM RECEBIDA (Incoming)")
    
    # Buscar tenant RBTec
    tenant = Tenant.objects.filter(name__icontains="RBTec").first()
    if not tenant:
        print("❌ Tenant RBTec não encontrado!")
        return False
    
    print(f"✅ Tenant encontrado: {tenant.name} (ID: {tenant.id})")
    
    # Buscar WhatsAppInstance
    instance = WhatsAppInstance.objects.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    if not instance:
        print("❌ WhatsAppInstance não encontrada!")
        return False
    
    print(f"✅ Instance encontrada: {instance.friendly_name}")
    print(f"   UUID: {instance.instance_name}")
    
    # Simular webhook de mensagem recebida
    webhook_data = {
        "event": "messages.upsert",
        "instance": instance.instance_name,  # UUID
        "data": {
            "key": {
                "remoteJid": "5517991253112@s.whatsapp.net",
                "fromMe": False,  # Mensagem RECEBIDA
                "id": "TEST_MSG_INCOMING_001"
            },
            "message": {
                "conversation": "Olá! Esta é uma mensagem de teste do contato"
            },
            "messageType": "conversation",
            "messageTimestamp": int(timezone.now().timestamp()),
            "pushName": "Paulo Bernal"
        }
    }
    
    print("\n📤 Enviando webhook simulado:")
    print(f"   Event: messages.upsert")
    print(f"   Direction: INCOMING (fromMe=False)")
    print(f"   Phone: +5517991253112")
    print(f"   Content: {webhook_data['data']['message']['conversation']}")
    
    try:
        handle_message_upsert(webhook_data, tenant)
        
        # Verificar se mensagem foi criada
        message = Message.objects.filter(message_id="TEST_MSG_INCOMING_001").first()
        
        if message:
            print(f"\n✅ SUCESSO! Mensagem criada:")
            print(f"   ID: {message.id}")
            print(f"   Direction: {message.direction}")
            print(f"   Content: {message.content}")
            print(f"   Status: {message.status}")
            print(f"   Conversation: {message.conversation_id}")
            return True
        else:
            print("\n❌ FALHA! Mensagem não foi criada no banco")
            return False
    
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_outgoing_message():
    """Testa envio de mensagem (do sistema)"""
    print_section("📤 TESTE 2: MENSAGEM ENVIADA (Outgoing)")
    
    tenant = Tenant.objects.filter(name__icontains="RBTec").first()
    instance = WhatsAppInstance.objects.filter(tenant=tenant, is_active=True).first()
    
    webhook_data = {
        "event": "messages.upsert",
        "instance": instance.instance_name,
        "data": {
            "key": {
                "remoteJid": "5517991253112@s.whatsapp.net",
                "fromMe": True,  # Mensagem ENVIADA
                "id": "TEST_MSG_OUTGOING_001"
            },
            "message": {
                "conversation": "Mensagem de teste enviada pelo sistema"
            },
            "messageType": "conversation",
            "messageTimestamp": int(timezone.now().timestamp()),
            "pushName": "Sistema"
        }
    }
    
    print("\n📤 Enviando webhook simulado:")
    print(f"   Event: messages.upsert")
    print(f"   Direction: OUTGOING (fromMe=True)")
    print(f"   Content: {webhook_data['data']['message']['conversation']}")
    
    try:
        handle_message_upsert(webhook_data, tenant)
        
        message = Message.objects.filter(message_id="TEST_MSG_OUTGOING_001").first()
        
        if message:
            print(f"\n✅ SUCESSO! Mensagem criada:")
            print(f"   Direction: {message.direction}")
            print(f"   Status: {message.status}")
            return True
        else:
            print("\n❌ FALHA! Mensagem não foi criada")
            return False
    
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        return False

def test_status_update():
    """Testa atualização de status (delivered/read)"""
    print_section("🔄 TESTE 3: ATUALIZAÇÃO DE STATUS")
    
    tenant = Tenant.objects.filter(name__icontains="RBTec").first()
    instance = WhatsAppInstance.objects.filter(tenant=tenant, is_active=True).first()
    
    # Primeiro criar uma mensagem
    message = Message.objects.filter(
        conversation__tenant=tenant,
        direction='outgoing'
    ).first()
    
    if not message:
        print("⚠️ Nenhuma mensagem outgoing encontrada, criando uma...")
        webhook_create = {
            "event": "messages.upsert",
            "instance": instance.instance_name,
            "data": {
                "key": {
                    "remoteJid": "5517991253112@s.whatsapp.net",
                    "fromMe": True,
                    "id": "TEST_STATUS_MSG_001"
                },
                "message": {"conversation": "Teste para status"},
                "messageType": "conversation",
                "messageTimestamp": int(timezone.now().timestamp())
            }
        }
        handle_message_upsert(webhook_create, tenant)
        message = Message.objects.get(message_id="TEST_STATUS_MSG_001")
    
    print(f"\n📋 Mensagem para teste:")
    print(f"   ID: {message.id}")
    print(f"   Message ID: {message.message_id}")
    print(f"   Status atual: {message.status}")
    
    # Testar update para DELIVERED
    print("\n📤 Testando update para DELIVERED...")
    webhook_delivered = {
        "event": "messages.update",
        "instance": instance.instance_name,
        "data": {
            "key": {
                "id": message.message_id
            },
            "update": {
                "status": "DELIVERY_ACK"
            }
        }
    }
    
    try:
        handle_message_update(webhook_delivered, tenant)
        message.refresh_from_db()
        
        if message.status == 'delivered':
            print(f"✅ Status atualizado: {message.status}")
        else:
            print(f"⚠️ Status não mudou: {message.status}")
    
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False
    
    # Testar update para READ
    print("\n📤 Testando update para READ...")
    webhook_read = {
        "event": "messages.update",
        "instance": instance.instance_name,
        "data": {
            "key": {
                "id": message.message_id
            },
            "update": {
                "status": "READ"
            }
        }
    }
    
    try:
        handle_message_update(webhook_read, tenant)
        message.refresh_from_db()
        
        if message.status == 'seen':
            print(f"✅ Status atualizado: {message.status}")
            return True
        else:
            print(f"⚠️ Status não mudou: {message.status}")
            return False
    
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

def check_current_state():
    """Verifica estado atual do banco"""
    print_section("📊 ESTADO ATUAL DO BANCO")
    
    tenant = Tenant.objects.filter(name__icontains="RBTec").first()
    
    if not tenant:
        print("❌ Tenant não encontrado")
        return
    
    print(f"\n🏢 Tenant: {tenant.name}")
    
    # Conversas
    conversations = Conversation.objects.filter(tenant=tenant)
    print(f"\n💬 Conversas: {conversations.count()}")
    for conv in conversations:
        print(f"   - {conv.contact_name or conv.contact_phone}: {conv.status}")
        print(f"     Department: {conv.department or 'Inbox'}")
    
    # Mensagens
    messages = Message.objects.filter(conversation__tenant=tenant).order_by('-created_at')[:5]
    print(f"\n📨 Últimas 5 mensagens:")
    for msg in messages:
        direction_icon = "📤" if msg.direction == 'outgoing' else "📥"
        status_icon = {
            'pending': '⏳',
            'sent': '✓',
            'delivered': '✓✓',
            'seen': '✓✓ (lido)'
        }.get(msg.status, '?')
        
        print(f"   {direction_icon} {msg.content[:50]}... [{status_icon}]")
        print(f"      Status: {msg.status} | ID: {msg.message_id}")

def main():
    print("\n" + "="*60)
    print("  🧪 TESTE COMPLETO DO FLUXO DE CHAT")
    print("="*60)
    
    # Estado atual
    check_current_state()
    
    # Executar testes
    results = []
    
    results.append(("Mensagem Recebida (Incoming)", test_incoming_message()))
    results.append(("Mensagem Enviada (Outgoing)", test_outgoing_message()))
    results.append(("Atualização de Status", test_status_update()))
    
    # Resumo
    print_section("📊 RESUMO DOS TESTES")
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print(f"\n📈 Total: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM! Sistema está funcionando corretamente.")
    else:
        print("\n⚠️ ALGUNS TESTES FALHARAM. Revisar logs acima.")

if __name__ == '__main__':
    main()

