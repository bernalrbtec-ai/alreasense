#!/usr/bin/env python
"""
Script para corrigir nomes das conversas via Railway Dashboard
Execute: Railway Dashboard → Shell → python backend/fix_conversation_names_railway.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.chat.models import Conversation
from apps.contacts.models import Contact
import re


def normalize_phone_for_search(phone: str) -> str:
    """Normaliza telefone para busca (remove formatação, garante formato E.164)."""
    if not phone:
        return phone
    
    clean = phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
    clean = ''.join(c for c in clean if c.isdigit() or c == '+')
    
    if clean and not clean.startswith('+'):
        if clean.startswith('55'):
            clean = '+' + clean
        else:
            clean = '+55' + clean
    
    return clean


def fix_conversation_names():
    print(f"\n{'='*60}")
    print('🔧 CORRIGINDO NOMES DAS CONVERSAS')
    print(f"{'='*60}\n")
    
    # Buscar todas as conversas individuais
    conversations = Conversation.objects.filter(
        conversation_type='individual'
    ).select_related('tenant')
    
    print(f"📋 Total de conversas individuais: {conversations.count()}\n")
    
    updated_count = 0
    not_found_count = 0
    already_correct_count = 0
    
    # Para cada conversa, buscar contato correspondente
    for conversation in conversations:
        # Normalizar telefone da conversa
        normalized_conv_phone = normalize_phone_for_search(conversation.contact_phone)
        
        # Buscar contato com telefone correspondente
        contact = None
        for c in Contact.objects.filter(tenant=conversation.tenant):
            normalized_contact_phone = normalize_phone_for_search(c.phone)
            if normalized_contact_phone == normalized_conv_phone:
                contact = c
                break
        
        if contact:
            # Verificar se precisa atualizar
            if conversation.contact_name != contact.name:
                old_name = conversation.contact_name
                conversation.contact_name = contact.name
                conversation.save(update_fields=['contact_name'])
                updated_count += 1
                print(f"✅ {conversation.contact_phone}: '{old_name}' → '{contact.name}'")
            else:
                already_correct_count += 1
        else:
            # Verificar se contact_name é apenas número (formato de telefone)
            if conversation.contact_name and re.match(r'^[\d\s\(\)\-]+$', conversation.contact_name):
                not_found_count += 1
                print(f"⚠️  {conversation.contact_phone}: '{conversation.contact_name}' (sem contato cadastrado)")
            else:
                already_correct_count += 1
    
    print(f"\n{'='*60}")
    print("✅ CORREÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"\n📊 Estatísticas:")
    print(f"   ✅ Conversas atualizadas: {updated_count}")
    print(f"   ✅ Conversas já corretas: {already_correct_count}")
    print(f"   ⚠️  Conversas sem contato: {not_found_count}")
    print(f"   📋 Total processadas: {conversations.count()}")


if __name__ == '__main__':
    fix_conversation_names()

