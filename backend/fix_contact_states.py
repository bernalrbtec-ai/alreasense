#!/usr/bin/env python
"""
Script para corrigir estados dos contatos baseado no DDD do telefone
"""
import os
import sys
import django

# Configurar Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'evosense.settings')
django.setup()

from apps.contacts.models import Contact
from apps.contacts.utils import get_state_from_phone

def fix_contact_states():
    """Corrige estados dos contatos baseado no DDD"""
    print("🔧 Corrigindo estados dos contatos...")
    
    # Buscar contatos sem estado
    contacts_without_state = Contact.objects.filter(state__isnull=True)
    print(f"📊 Contatos sem estado: {contacts_without_state.count()}")
    
    # Buscar contatos com estado vazio
    contacts_empty_state = Contact.objects.filter(state='')
    print(f"📊 Contatos com estado vazio: {contacts_empty_state.count()}")
    
    total_to_fix = contacts_without_state.count() + contacts_empty_state.count()
    print(f"📊 Total a corrigir: {total_to_fix}")
    
    if total_to_fix == 0:
        print("✅ Todos os contatos já têm estado definido!")
        return
    
    # Corrigir contatos sem estado
    fixed_count = 0
    for contact in contacts_without_state:
        if contact.phone:
            state = get_state_from_phone(contact.phone)
            if state:
                contact.state = state
                contact.save(update_fields=['state'])
                fixed_count += 1
                print(f"  ✅ {contact.name} ({contact.phone}) → {state}")
    
    # Corrigir contatos com estado vazio
    for contact in contacts_empty_state:
        if contact.phone:
            state = get_state_from_phone(contact.phone)
            if state:
                contact.state = state
                contact.save(update_fields=['state'])
                fixed_count += 1
                print(f"  ✅ {contact.name} ({contact.phone}) → {state}")
    
    print(f"\n🎉 Corrigidos {fixed_count} contatos!")
    
    # Mostrar estatísticas finais
    print("\n📊 Estatísticas finais:")
    from django.db.models import Count
    state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
    for item in state_counts:
        state_val = item['state'] if item['state'] else 'NULL'
        print(f"  • {state_val}: {item['count']} contatos")

if __name__ == "__main__":
    fix_contact_states()



