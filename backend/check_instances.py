#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance

instances = WhatsAppInstance.objects.filter(connection_state='open')
print(f'\n📱 Instâncias WhatsApp Conectadas: {instances.count()}\n')

if instances.exists():
    for i in instances:
        print(f'  ✓ {i.friendly_name}')
        print(f'    Telefone: {i.phone_number}')
        print(f'    API Key: {i.api_key[:20]}...')
        print()
else:
    print('  ❌ Nenhuma instância conectada!')
    print('  📋 Configure uma instância em: Admin → Notificações → Instâncias WhatsApp\n')

