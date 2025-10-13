#!/usr/bin/env python
"""
Script para limpar TODOS os dados do sistema
- Contatos
- Campanhas
- CampaignContacts
- CampaignLogs
- Messages (campanhas)
- WhatsApp Instances (health scores)
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import transaction
from apps.contacts.models import Contact
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog, CampaignMessage
from apps.chat_messages.models import Message
from apps.notifications.models import WhatsAppInstance
from apps.connections.models import EvolutionConnection

def clear_all_data():
    """Limpa todos os dados do sistema"""
    print("🧹 INICIANDO LIMPEZA COMPLETA DO SISTEMA...")
    
    with transaction.atomic():
        try:
            # 1. Limpar CampaignContacts
            campaign_contacts_count = CampaignContact.objects.count()
            CampaignContact.objects.all().delete()
            print(f"✅ Removidos {campaign_contacts_count} CampaignContacts")
            
            # 2. Limpar CampaignLogs
            campaign_logs_count = CampaignLog.objects.count()
            CampaignLog.objects.all().delete()
            print(f"✅ Removidos {campaign_logs_count} CampaignLogs")
            
            # 3. Limpar CampaignMessages
            campaign_messages_count = CampaignMessage.objects.count()
            CampaignMessage.objects.all().delete()
            print(f"✅ Removidos {campaign_messages_count} CampaignMessages")
            
            # 4. Limpar Campaigns
            campaigns_count = Campaign.objects.count()
            Campaign.objects.all().delete()
            print(f"✅ Removidas {campaigns_count} Campanhas")
            
            # 5. Limpar Messages (todas - campanhas e chat)
            messages_count = Message.objects.count()
            Message.objects.all().delete()
            print(f"✅ Removidas {messages_count} Messages")
            
            # 6. Limpar Contatos
            contacts_count = Contact.objects.count()
            Contact.objects.all().delete()
            print(f"✅ Removidos {contacts_count} Contatos")
            
            # 7. Reset WhatsApp Instances health scores
            instances = WhatsAppInstance.objects.all()
            for instance in instances:
                instance.health_score = 100
                instance.msgs_sent_today = 0
                instance.msgs_delivered_today = 0
                instance.msgs_read_today = 0
                instance.msgs_failed_today = 0
                instance.save()
            print(f"✅ Resetados {instances.count()} WhatsApp Instances")
            
            # 8. Reset Evolution Connections status
            connections = EvolutionConnection.objects.all()
            for connection in connections:
                connection.status = 'active'
                connection.save()
            print(f"✅ Resetados {connections.count()} Evolution Connections")
            
            print("\n🎉 LIMPEZA COMPLETA FINALIZADA!")
            print("📊 RESUMO:")
            print(f"   - CampaignContacts: {campaign_contacts_count} removidos")
            print(f"   - CampaignLogs: {campaign_logs_count} removidos")
            print(f"   - CampaignMessages: {campaign_messages_count} removidos")
            print(f"   - Campaigns: {campaigns_count} removidas")
            print(f"   - Messages: {messages_count} removidas")
            print(f"   - Contatos: {contacts_count} removidos")
            print(f"   - WhatsApp Instances: {instances.count()} resetados")
            print(f"   - Evolution Connections: {connections.count()} resetados")
            
        except Exception as e:
            print(f"❌ Erro durante limpeza: {str(e)}")
            raise

if __name__ == '__main__':
    confirm = input("⚠️  ATENÇÃO: Isso vai apagar TODOS os contatos e campanhas do sistema! Digite 'CONFIRMAR' para continuar: ")
    
    if confirm == 'CONFIRMAR':
        clear_all_data()
    else:
        print("❌ Operação cancelada.")
