"""
Comando Django para corrigir contact_name das conversas com nomes de contatos existentes
"""
from django.core.management.base import BaseCommand
from apps.chat.models import Conversation
from apps.contacts.models import Contact
import re


def normalize_phone_for_search(phone: str) -> str:
    """
    Normaliza telefone para busca (remove formatação, garante formato E.164).
    """
    if not phone:
        return phone
    
    # Remover formatação (parênteses, hífens, espaços, @s.whatsapp.net)
    clean = phone.replace('@s.whatsapp.net', '').replace('@g.us', '')
    clean = ''.join(c for c in clean if c.isdigit() or c == '+')
    
    # Garantir formato E.164 (com +)
    if clean and not clean.startswith('+'):
        # Se começa com 55, adicionar +
        if clean.startswith('55'):
            clean = '+' + clean
        else:
            # Assumir Brasil (+55)
            clean = '+55' + clean
    
    return clean


class Command(BaseCommand):
    help = 'Corrige contact_name das conversas usando nomes de contatos existentes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('🔧 CORRIGINDO NOMES DAS CONVERSAS'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        # Buscar todas as conversas individuais
        conversations = Conversation.objects.filter(
            conversation_type='individual'
        ).select_related('tenant')
        
        self.stdout.write(f"📋 Total de conversas individuais: {conversations.count()}\n")
        
        updated_count = 0
        not_found_count = 0
        
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
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ {conversation.contact_phone}: '{old_name}' → '{contact.name}'"
                        )
                    )
            else:
                # Verificar se contact_name é apenas número (formato de telefone)
                # Se for, marcar como não encontrado
                if conversation.contact_name and re.match(r'^[\d\s\(\)\-]+$', conversation.contact_name):
                    not_found_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  {conversation.contact_phone}: '{conversation.contact_name}' (sem contato cadastrado)"
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS("✅ CORREÇÃO CONCLUÍDA!"))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"\n📊 Estatísticas:")
        self.stdout.write(f"   ✅ Conversas atualizadas: {updated_count}")
        self.stdout.write(f"   ⚠️  Conversas sem contato: {not_found_count}")
        self.stdout.write(f"   📋 Total processadas: {conversations.count()}")

