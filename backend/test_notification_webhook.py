#!/usr/bin/env python
"""
Script para testar o webhook de notificações localmente
"""
import os
import sys
import django
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import CampaignNotification, Campaign, CampaignContact
from apps.contacts.models import Contact
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.notifications.models import WhatsAppInstance

def test_notification_creation():
    """Testar criação de notificação"""
    print("🧪 TESTANDO CRIAÇÃO DE NOTIFICAÇÃO")
    print("=" * 50)
    
    try:
        # Buscar dados existentes
        tenant = Tenant.objects.first()
        campaign = Campaign.objects.first()
        contact = Contact.objects.first()
        
        if not all([tenant, campaign, contact]):
            print("❌ Dados necessários não encontrados:")
            print(f"   Tenant: {'✅' if tenant else '❌'}")
            print(f"   Campaign: {'✅' if campaign else '❌'}")
            print(f"   Contact: {'✅' if contact else '❌'}")
            return
        
        # Buscar ou criar CampaignContact
        campaign_contact, created = CampaignContact.objects.get_or_create(
            campaign=campaign,
            contact=contact,
            defaults={
                'tenant': tenant,
                'status': 'sent'
            }
        )
        
        # Buscar ou criar WhatsAppInstance
        instance, created = WhatsAppInstance.objects.get_or_create(
            tenant=tenant,
            phone_number=contact.phone,
            defaults={
                'friendly_name': f'test_instance_{contact.phone}',
                'instance_name': f'test_{contact.phone}',
                'status': 'active'
            }
        )
        
        # Criar notificação de teste
        notification = CampaignNotification.objects.create(
            tenant=tenant,
            campaign=campaign,
            contact=contact,
            campaign_contact=campaign_contact,
            instance=instance,
            notification_type='response',
            status='unread',
            received_message='Teste de mensagem de resposta',
            whatsapp_message_id='test_msg_123',
            details={
                'message_type': 'text',
                'chat_id': f'{contact.phone}@s.whatsapp.net',
                'test': True
            }
        )
        
        print(f"✅ Notificação criada com sucesso!")
        print(f"   ID: {notification.id}")
        print(f"   Contato: {notification.contact.name}")
        print(f"   Campanha: {notification.campaign.name}")
        print(f"   Mensagem: {notification.received_message}")
        print(f"   Status: {notification.status}")
        
        # Testar métodos do modelo
        print("\n🔧 TESTANDO MÉTODOS DO MODELO:")
        
        # Marcar como lida
        notification.mark_as_read()
        print(f"✅ Marcação como lida: {notification.status}")
        
        # Marcar como respondida
        notification.mark_as_replied("Resposta de teste", None)
        print(f"✅ Marcação como respondida: {notification.status}")
        print(f"   Resposta: {notification.sent_reply}")
        
        # Limpar notificação de teste
        notification.delete()
        print("✅ Notificação de teste removida")
        
        print("\n🎉 TESTE CONCLUÍDO COM SUCESSO!")
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {str(e)}")
        import traceback
        traceback.print_exc()

def test_webhook_simulation():
    """Simular recebimento de webhook"""
    print("\n🧪 SIMULANDO WEBHOOK messages.upsert")
    print("=" * 50)
    
    # Simular dados do webhook
    webhook_data = {
        "event": "messages.upsert",
        "data": {
            "instance": "test_instance",
            "messages": [{
                "key": {
                    "remoteJid": "5517999123456@s.whatsapp.net",
                    "id": "test_msg_456",
                    "fromMe": False
                },
                "message": {
                    "conversation": "Olá, recebi sua mensagem!"
                },
                "messageTimestamp": int(datetime.now().timestamp())
            }]
        }
    }
    
    print(f"📥 Dados do webhook simulados:")
    print(json.dumps(webhook_data, indent=2, ensure_ascii=False))
    
    print("\n✅ Simulação de webhook concluída!")
    print("   (Para teste real, seria necessário configurar Evolution API)")

if __name__ == "__main__":
    test_notification_creation()
    test_webhook_simulation()
