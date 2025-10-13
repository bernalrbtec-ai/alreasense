#!/usr/bin/env python
"""
Script para debugar o status das campanhas e entender por que param de enviar
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign, CampaignContact
from apps.notifications.models import WhatsAppInstance
from django.utils import timezone

def debug_campaign_status():
    print("🔍 DEBUG CAMPANHA STATUS")
    print("=" * 50)
    
    # Buscar campanhas ativas
    running_campaigns = Campaign.objects.filter(status='running')
    print(f"📊 Campanhas rodando: {running_campaigns.count()}")
    
    for campaign in running_campaigns:
        print(f"\n🎯 CAMPANHA: {campaign.name}")
        print(f"   ID: {campaign.id}")
        print(f"   Status: {campaign.status}")
        print(f"   Última mensagem: {campaign.last_message_sent_at}")
        print(f"   Próxima agendada: {campaign.next_message_scheduled_at}")
        
        # Verificar contatos
        total_contacts = campaign.campaign_contacts.count()
        pending_contacts = campaign.campaign_contacts.filter(status='pending').count()
        sent_contacts = campaign.campaign_contacts.filter(status='sent').count()
        delivered_contacts = campaign.campaign_contacts.filter(status='delivered').count()
        failed_contacts = campaign.campaign_contacts.filter(status='failed').count()
        
        print(f"   📋 Contatos:")
        print(f"      Total: {total_contacts}")
        print(f"      Pendentes: {pending_contacts}")
        print(f"      Enviados: {sent_contacts}")
        print(f"      Entregues: {delivered_contacts}")
        print(f"      Falhas: {failed_contacts}")
        
        # Verificar instâncias
        print(f"   🔄 Instâncias:")
        for instance in campaign.instances.all():
            print(f"      {instance.friendly_name}:")
            print(f"         Status: {instance.connection_state}")
            print(f"         Health: {instance.health_score}")
            print(f"         Msgs hoje: {instance.msgs_sent_today}/{campaign.daily_limit_per_instance}")
            print(f"         Última msg: {instance.last_message_sent_at}")
        
        # Verificar próximo contato
        next_contact = campaign.campaign_contacts.filter(status='pending').first()
        if next_contact:
            print(f"   📱 Próximo contato: {next_contact.contact.name} ({next_contact.contact.phone})")
        else:
            print(f"   📱 Próximo contato: NENHUM (todos processados)")
        
        # Verificar se deveria estar rodando
        if pending_contacts == 0:
            print(f"   ⚠️  PROBLEMA: Não há contatos pendentes, mas campanha ainda está 'running'")
        elif campaign.next_message_scheduled_at and campaign.next_message_scheduled_at > timezone.now():
            print(f"   ⏰ Próxima mensagem agendada para: {campaign.next_message_scheduled_at}")
        else:
            print(f"   ✅ Deveria estar enviando mensagens agora")

if __name__ == "__main__":
    debug_campaign_status()
