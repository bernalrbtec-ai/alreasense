"""
Script para debugar webhook do chat
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.chat.models import Conversation, Message
from apps.tenancy.models import Tenant

print("=" * 60)
print("🔍 DIAGNÓSTICO DO CHAT")
print("=" * 60)

# 1. Verificar Evolution Connection
print("\n1️⃣ EVOLUTION CONNECTIONS:")
print("-" * 60)
connections = EvolutionConnection.objects.all()
for conn in connections:
    print(f"   📱 {conn.name}")
    print(f"      Tenant: {conn.tenant.name}")
    print(f"      Base URL: {conn.base_url}")
    print(f"      Webhook: {conn.webhook_url}")
    print(f"      Status: {conn.status}")
    print(f"      Active: {conn.is_active}")
    print()

# 2. Verificar conversas
print("\n2️⃣ CONVERSAS NO CHAT:")
print("-" * 60)
conversations = Conversation.objects.all().order_by('-created_at')[:5]
if conversations:
    for conv in conversations:
        print(f"   💬 {conv.contact_name or conv.contact_phone}")
        print(f"      Tenant: {conv.tenant.name}")
        print(f"      Department: {conv.department.name if conv.department else 'Inbox'}")
        print(f"      Status: {conv.status}")
        print(f"      Última msg: {conv.last_message_at}")
        
        # Últimas 3 mensagens
        messages = Message.objects.filter(conversation=conv).order_by('-created_at')[:3]
        if messages:
            print(f"      Últimas mensagens:")
            for msg in messages:
                direction_icon = "📤" if msg.direction == "outgoing" else "📥"
                print(f"         {direction_icon} {msg.content[:50]}... ({msg.status})")
        print()
else:
    print("   ⚠️  Nenhuma conversa encontrada")

# 3. Verificar últimas mensagens
print("\n3️⃣ ÚLTIMAS MENSAGENS DO CHAT:")
print("-" * 60)
messages = Message.objects.all().order_by('-created_at')[:10]
if messages:
    for msg in messages:
        direction_icon = "📤" if msg.direction == "outgoing" else "📥"
        print(f"   {direction_icon} {msg.created_at.strftime('%H:%M:%S')}")
        print(f"      Conversa: {msg.conversation.contact_phone}")
        print(f"      Conteúdo: {msg.content[:80]}")
        print(f"      Status: {msg.status}")
        print(f"      Message ID: {msg.message_id}")
        print()
else:
    print("   ⚠️  Nenhuma mensagem encontrada")

# 4. Testar webhook URL
print("\n4️⃣ TESTE DE WEBHOOK:")
print("-" * 60)
webhook_url = "https://alreasense-backend-production.up.railway.app/webhooks/evolution"
print(f"   URL do Webhook: {webhook_url}")
print(f"   ✅ A Evolution API deve estar configurada para enviar eventos para esta URL")
print()

# 5. Estatísticas
print("\n5️⃣ ESTATÍSTICAS:")
print("-" * 60)
total_conversations = Conversation.objects.count()
total_messages = Message.objects.count()
pending_conversations = Conversation.objects.filter(status='pending').count()
open_conversations = Conversation.objects.filter(status='open').count()

print(f"   Total de conversas: {total_conversations}")
print(f"   Total de mensagens: {total_messages}")
print(f"   Conversas pendentes (Inbox): {pending_conversations}")
print(f"   Conversas abertas: {open_conversations}")

print("\n" + "=" * 60)
print("✅ DIAGNÓSTICO CONCLUÍDO")
print("=" * 60)

