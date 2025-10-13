#!/usr/bin/env python
"""
Script para corrigir contadores de mensagens no dashboard
Migra mensagens de campanhas para o modelo Message
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import CampaignContact
from apps.chat_messages.models import Message
from apps.tenancy.models import Tenant
from django.utils import timezone

def migrate_campaign_messages():
    """Migra mensagens de campanhas para o modelo Message"""
    
    print("🔧 Iniciando migração de mensagens de campanhas...")
    
    # Buscar todas as mensagens de campanha enviadas
    campaign_contacts = CampaignContact.objects.filter(
        status='sent',
        sent_at__isnull=False
    ).select_related('campaign', 'contact', 'campaign__tenant')
    
    total_migrated = 0
    total_skipped = 0
    
    for campaign_contact in campaign_contacts:
        # Verificar se já existe no modelo Message
        existing_message = Message.objects.filter(
            tenant=campaign_contact.campaign.tenant,
            chat_id=f"campaign_{campaign_contact.campaign.id}_{campaign_contact.contact.id}",
            sender=f"campaign_{campaign_contact.campaign.id}"
        ).first()
        
        if existing_message:
            total_skipped += 1
            continue
        
        # Criar mensagem no modelo Message
        message_text = campaign_contact.message_used.content if campaign_contact.message_used else "Mensagem de campanha"
        
        Message.objects.create(
            tenant=campaign_contact.campaign.tenant,
            connection=None,  # Não temos conexão direta
            chat_id=f"campaign_{campaign_contact.campaign.id}_{campaign_contact.contact.id}",
            sender=f"campaign_{campaign_contact.campaign.id}",
            text=message_text,
            created_at=campaign_contact.sent_at or timezone.now()
        )
        
        total_migrated += 1
        
        if total_migrated % 100 == 0:
            print(f"   Migradas: {total_migrated} mensagens...")
    
    print(f"✅ Migração concluída!")
    print(f"   📊 Total migradas: {total_migrated}")
    print(f"   ⏭️  Total ignoradas (já existiam): {total_skipped}")
    
    return total_migrated, total_skipped

def verify_counters():
    """Verifica se os contadores estão funcionando"""
    
    print("\n🔍 Verificando contadores...")
    
    for tenant in Tenant.objects.all():
        # Contar mensagens no modelo Message
        total_messages = Message.objects.filter(tenant=tenant).count()
        
        # Contar mensagens de campanhas
        campaign_messages = CampaignContact.objects.filter(
            campaign__tenant=tenant,
            status='sent'
        ).count()
        
        print(f"   🏢 {tenant.name}:")
        print(f"      📨 Mensagens no modelo Message: {total_messages}")
        print(f"      📤 Mensagens de campanhas: {campaign_messages}")
        
        # Verificar últimas 24h
        yesterday = timezone.now() - timedelta(days=1)
        messages_24h = Message.objects.filter(
            tenant=tenant,
            created_at__gte=yesterday
        ).count()
        
        campaign_messages_24h = CampaignContact.objects.filter(
            campaign__tenant=tenant,
            status='sent',
            sent_at__gte=yesterday
        ).count()
        
        print(f"      📅 Últimas 24h - Message: {messages_24h}, Campanhas: {campaign_messages_24h}")

if __name__ == "__main__":
    print("🚀 Script de correção de contadores de mensagens")
    print("=" * 50)
    
    try:
        # Migrar mensagens
        migrated, skipped = migrate_campaign_messages()
        
        # Verificar contadores
        verify_counters()
        
        print("\n✅ Script executado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante execução: {str(e)}")
        sys.exit(1)
