#!/usr/bin/env python
"""Verificar contatos da RBTec"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.contacts.models import Contact
from apps.tenancy.models import Tenant
from django.db.models import Count

tenant = Tenant.objects.filter(name='RBTec Informática').first()

if not tenant:
    print("❌ Tenant 'RBTec Informática' não encontrado")
    exit(1)

total = Contact.objects.filter(tenant=tenant).count()
print(f"\n📊 Total de contatos: {total}")

# Primeiros 10
print(f"\n📋 Primeiros 10 contatos:")
for i, contact in enumerate(Contact.objects.filter(tenant=tenant).order_by('id')[:10]):
    print(f"   {i+1}. {contact.name:20s} | Fone: {contact.phone:15s} | Estado: {contact.state or 'N/A':3s}")

# Contagem por estado
print(f"\n📍 Contatos por Estado (inferidos pelo DDD):")
by_state = Contact.objects.filter(tenant=tenant).exclude(state__isnull=True).values('state').annotate(count=Count('id')).order_by('-count')

total_with_state = sum(item['count'] for item in by_state)
total_without_state = total - total_with_state

for item in by_state:
    print(f"   {item['state']}: {item['count']:3d} contatos")

if total_without_state > 0:
    print(f"   (Sem estado): {total_without_state}")

print(f"\n✅ Total com estado inferido: {total_with_state}/{total} ({total_with_state/total*100:.1f}%)")




