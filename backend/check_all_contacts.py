#!/usr/bin/env python
"""Verificar todos os contatos e imports"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.contacts.models import Contact, ContactImport
from apps.tenancy.models import Tenant

print("\n" + "="*80)
print("📊 VERIFICAÇÃO DE CONTATOS E IMPORTS")
print("="*80)

# Listar todos os tenants
print("\n1️⃣ Tenants no sistema:")
for tenant in Tenant.objects.all():
    contact_count = Contact.objects.filter(tenant=tenant).count()
    print(f"   {tenant.name}: {contact_count} contatos")

# Listar imports recentes
print("\n2️⃣ Imports recentes (últimos 5):")
for imp in ContactImport.objects.all().order_by('-created_at')[:5]:
    print(f"\n   ID: {imp.id}")
    print(f"   Tenant: {imp.tenant.name if imp.tenant else 'N/A'}")
    print(f"   Arquivo: {imp.file_name}")
    print(f"   Status: {imp.status}")
    print(f"   Total: {imp.total_rows}")
    print(f"   Criados: {imp.created_count}")
    print(f"   Erros: {imp.error_count}")
    if imp.error_count > 0 and imp.errors:
        print(f"   Primeiros erros: {imp.errors[:2]}")

# Total geral
total_all = Contact.objects.count()
print(f"\n3️⃣ Total de contatos no sistema: {total_all}")

print("\n" + "="*80 + "\n")




