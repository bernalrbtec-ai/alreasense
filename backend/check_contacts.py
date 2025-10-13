#!/usr/bin/env python
"""
Script para verificar contatos importados
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.contacts.models import Contact

def check_contacts():
    """Verifica contatos importados"""
    print("📋 VERIFICANDO CONTATOS IMPORTADOS...")
    
    contacts = Contact.objects.all()
    total = contacts.count()
    
    print(f"📊 Total de contatos: {total}")
    
    if total > 0:
        print("\n🔍 Últimos 10 contatos:")
        for i, contact in enumerate(contacts[:10], 1):
            referred_by = contact.referred_by or "Não informado"
            print(f"  {i}. {contact.name} ({contact.phone}) - Quem Indicou: {referred_by}")
        
        # Verificar quantos têm "referred_by"
        with_referred = contacts.filter(referred_by__isnull=False).exclude(referred_by='').count()
        print(f"\n📈 Contatos com 'Quem Indicou': {with_referred}/{total}")
        
        if with_referred > 0:
            print("\n🎯 Exemplos de 'Quem Indicou':")
            referred_contacts = contacts.filter(referred_by__isnull=False).exclude(referred_by='')[:5]
            for contact in referred_contacts:
                print(f"  - {contact.name}: {contact.referred_by}")
    else:
        print("❌ Nenhum contato encontrado!")

if __name__ == '__main__':
    check_contacts()
