#!/usr/bin/env python
"""
Script para zerar todas as conversas via Railway Dashboard
⚠️ ATENÇÃO: Esta operação é IRREVERSÍVEL!

Execute: Railway Dashboard → Shell → python backend/zerar_conversas_railway.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import transaction
from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction


def clear_all_conversations(tenant_id=None, keep_messages=False):
    print(f"\n{'='*60}")
    print('⚠️  ZERAR TODAS AS CONVERSAS')
    print(f"{'='*60}\n")
    
    # Buscar conversas
    if tenant_id:
        from apps.tenancy.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            conversations = Conversation.objects.filter(tenant=tenant)
            print(f"📋 Tenant: {tenant.name}")
        except Tenant.DoesNotExist:
            print(f"❌ Tenant não encontrado: {tenant_id}")
            return
    else:
        conversations = Conversation.objects.all()
        print("📋 Todos os tenants")
    
    total_conversations = conversations.count()
    
    if total_conversations == 0:
        print("✅ Nenhuma conversa encontrada!")
        return
    
    # Contar mensagens e anexos
    if not keep_messages:
        total_messages = Message.objects.filter(conversation__in=conversations).count()
        total_attachments = MessageAttachment.objects.filter(message__conversation__in=conversations).count()
        total_reactions = MessageReaction.objects.filter(message__conversation__in=conversations).count()
    else:
        total_messages = 0
        total_attachments = 0
        total_reactions = 0
    
    print(f"\n📊 Estatísticas:")
    print(f"   📋 Conversas: {total_conversations}")
    if not keep_messages:
        print(f"   💬 Mensagens: {total_messages}")
        print(f"   📎 Anexos: {total_attachments}")
        print(f"   👍 Reações: {total_reactions}")
    
    print(f"\n⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!")
    print(f"   Todas as conversas serão deletadas permanentemente.")
    if not keep_messages:
        print(f"   Todas as mensagens, anexos e reações também serão deletados.")
    
    # Confirmação
    print(f"\n❓ Digite 'SIM' para confirmar:")
    user_input = input().strip()
    if user_input != 'SIM':
        print('❌ Operação cancelada.')
        return
    
    # Executar deleção
    print(f"\n🗑️  Deletando...")
    
    try:
        with transaction.atomic():
            deleted_conversations = 0
            deleted_messages = 0
            deleted_attachments = 0
            deleted_reactions = 0
            
            if not keep_messages:
                # Deletar reações primeiro (dependem de mensagens)
                deleted_reactions = MessageReaction.objects.filter(
                    message__conversation__in=conversations
                ).delete()[0]
                
                # Deletar anexos
                deleted_attachments = MessageAttachment.objects.filter(
                    message__conversation__in=conversations
                ).delete()[0]
                
                # Deletar mensagens
                deleted_messages = Message.objects.filter(
                    conversation__in=conversations
                ).delete()[0]
            
            # Deletar conversas
            deleted_conversations = conversations.delete()[0]
            
            print(f'\n✅ Deleção concluída!')
            print(f"   📋 Conversas deletadas: {deleted_conversations}")
            if not keep_messages:
                print(f"   💬 Mensagens deletadas: {deleted_messages}")
                print(f"   📎 Anexos deletados: {deleted_attachments}")
                print(f"   👍 Reações deletadas: {deleted_reactions}")
            
    except Exception as e:
        print(f'\n❌ Erro ao deletar: {e}')
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    # Para zerar todas as conversas de todos os tenants:
    clear_all_conversations()
    
    # Para zerar apenas de um tenant específico:
    # clear_all_conversations(tenant_id='uuid-do-tenant')
    
    # Para manter mensagens (apenas deletar conversas):
    # clear_all_conversations(keep_messages=True)

