#!/usr/bin/env python
"""Verificar contatos importados"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.contacts.models import Contact
from apps.tenancy.models import Tenant

tenant = Tenant.objects.filter(name='Teste Campanhas').first()

if not tenant:
    print("❌ Tenant 'Teste Campanhas' não encontrado")
    exit(1)

total = Contact.objects.filter(tenant=tenant).count()
print(f"\n📊 Total de contatos no tenant '{tenant.name}': {total}")

if total > 0:
    print(f"\n📋 Primeiros 10 contatos:")
    for i, contact in enumerate(Contact.objects.filter(tenant=tenant)[:10]):
        print(f"   {i+1}. {contact.name} - {contact.phone} - Estado: {contact.state or 'N/A'}")
    
    # Contagem por estado
    from django.db.models import Count
    by_state = Contact.objects.filter(tenant=tenant).values('state').annotate(count=Count('id')).order_by('-count')
    
    print(f"\n📍 Contatos por Estado:")
    for item in by_state[:10]:
        state = item['state'] or 'Sem Estado'
        print(f"   {state}: {item['count']}")
else:
    print("\n⚠️ Nenhum contato encontrado")



