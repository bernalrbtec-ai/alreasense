#!/usr/bin/env python
"""
Script para criar campanha de teste para notificações
"""
import os
import sys
import django
from datetime import timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign
from apps.contacts.models import Contact
from apps.tenancy.models import Tenant
from django.utils import timezone

def create_test_campaign():
    """Criar campanha de teste para notificações"""
    print('🧪 CRIANDO CAMPANHA DE TESTE PARA NOTIFICAÇÕES')
    print('=' * 60)

    # Buscar tenant
    tenant = Tenant.objects.first()
    print(f'📊 Tenant: {tenant.name if tenant else "Nenhum"}')

    # Buscar contatos
    contacts = Contact.objects.filter(tenant=tenant, is_active=True)[:5]
    print(f'📊 Contatos disponíveis: {contacts.count()}')

    if contacts.count() == 0:
        print('❌ Nenhum contato encontrado. Criando contato de teste...')
        contact = Contact.objects.create(
            tenant=tenant,
            name='Contato Teste Notificação',
            phone='5517999123456',
            email='teste@exemplo.com',
            is_active=True
        )
        print(f'✅ Contato criado: {contact.name}')
    else:
        contact = contacts.first()
        print(f'✅ Usando contato: {contact.name}')

    # Criar campanha de teste
    campaign = Campaign.objects.create(
        tenant=tenant,
        name='Teste Notificações - ' + timezone.now().strftime('%d/%m %H:%M'),
        description='Campanha para testar sistema de notificações',
        rotation_mode='intelligent',
        interval_min=30,
        interval_max=60,
        daily_limit_per_instance=50,
        pause_on_health_below=30,
        scheduled_at=timezone.now() + timedelta(minutes=5),
        status='draft',
        total_contacts=1,
        messages_sent=0,
        messages_delivered=0,
        messages_read=0,
        messages_failed=0,
        current_instance_index=0
    )

    print(f'✅ Campanha criada: {campaign.name}')
    print(f'   Status: {campaign.status}')
    print(f'   Agendada para: {campaign.scheduled_at}')
    print(f'   Contatos: {campaign.total_contacts}')
    
    return campaign

if __name__ == "__main__":
    create_test_campaign()
