#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'evosense.settings')
django.setup()

from apps.contacts.models import Contact

def debug_contacts_state():
    """Debug para verificar estados dos contatos"""
    print("🔍 Verificando estados dos contatos...")
    
    # Buscar todos os contatos
    contacts = Contact.objects.all()[:10]
    
    print(f"\n📊 Total de contatos no sistema: {Contact.objects.count()}")
    print(f"📊 Primeiros 10 contatos:")
    
    for contact in contacts:
        print(f"  • {contact.name} | {contact.phone} | Estado: '{contact.state}' | DDD: {contact.phone[:2] if contact.phone else 'N/A'}")
    
    # Contar por estado
    print(f"\n📊 Contagem por estado:")
    from django.db.models import Count
    state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
    
    for item in state_counts:
        print(f"  • {item['state'] or 'NULL'}: {item['count']} contatos")
    
    # Verificar se há contatos sem estado
    no_state = Contact.objects.filter(state__isnull=True).count()
    print(f"\n⚠️ Contatos sem estado: {no_state}")

if __name__ == "__main__":
    debug_contacts_state()



