"""
Script para limpar TODOS os dados do chat via Django ORM.
Mais seguro que SQL direto pois respeita as foreign keys automaticamente.
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
current_dir = Path(__file__).parent
backend_dir = current_dir / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from apps.chat.models import Conversation, Message, MessageAttachment
from apps.tenancy.models import Tenant


def show_stats(label="ESTATÍSTICAS"):
    """Mostra estatísticas atuais do banco."""
    print(f"\n{'='*80}")
    print(f"📊 {label}")
    print(f"{'='*80}")
    
    # Por tenant
    tenants = Tenant.objects.all()
    
    total_conversations = 0
    total_messages = 0
    total_attachments = 0
    
    for tenant in tenants:
        conv_count = Conversation.objects.filter(tenant=tenant).count()
        msg_count = Message.objects.filter(conversation__tenant=tenant).count()
        att_count = MessageAttachment.objects.filter(
            message__conversation__tenant=tenant
        ).count()
        
        total_conversations += conv_count
        total_messages += msg_count
        total_attachments += att_count
        
        if conv_count > 0 or msg_count > 0 or att_count > 0:
            print(f"\n📋 {tenant.name}:")
            print(f"   Conversas: {conv_count}")
            print(f"   Mensagens: {msg_count}")
            print(f"   Anexos: {att_count}")
    
    print(f"\n{'='*80}")
    print(f"📊 TOTAL GERAL:")
    print(f"   Conversas: {total_conversations}")
    print(f"   Mensagens: {total_messages}")
    print(f"   Anexos: {total_attachments}")
    print(f"{'='*80}")
    
    return total_conversations, total_messages, total_attachments


def clear_all_chat_data():
    """Limpa todos os dados do chat."""
    
    print("\n" + "="*80)
    print("🗑️  LIMPEZA COMPLETA DO CHAT")
    print("="*80)
    
    # Mostrar estatísticas antes
    total_conv, total_msg, total_att = show_stats("ANTES DA LIMPEZA")
    
    if total_conv == 0 and total_msg == 0 and total_att == 0:
        print("\n✅ Nenhum dado para deletar! Banco já está limpo.")
        return
    
    # Confirmação
    print("\n" + "="*80)
    print("⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!")
    print("   Todos os dados do chat serão DELETADOS:")
    print(f"   - {total_conv} conversas")
    print(f"   - {total_msg} mensagens")
    print(f"   - {total_att} anexos")
    print("\n   Os seguintes dados NÃO serão afetados:")
    print("   ✅ Usuários")
    print("   ✅ Departamentos")
    print("   ✅ Tenants")
    print("   ✅ Instâncias WhatsApp")
    print("="*80)
    
    confirm1 = input("\n❓ Digite 'DELETAR' para continuar: ").strip()
    if confirm1 != 'DELETAR':
        print("\n❌ Operação cancelada.")
        return
    
    print("\n⚠️  ÚLTIMA CONFIRMAÇÃO!")
    confirm2 = input("❓ Digite 'SIM TENHO CERTEZA' para prosseguir: ").strip()
    if confirm2 != 'SIM TENHO CERTEZA':
        print("\n❌ Operação cancelada.")
        return
    
    # Deletar dados
    print("\n🗑️  Iniciando limpeza...")
    
    try:
        with transaction.atomic():
            # Django ORM cuida da ordem correta automaticamente
            # Cascade delete funciona: Conversas → Mensagens → Anexos
            
            print(f"\n1️⃣ Deletando {total_att} anexos...")
            deleted_att = MessageAttachment.objects.all().delete()[0]
            print(f"   ✅ {deleted_att} anexos deletados")
            
            print(f"\n2️⃣ Deletando {total_msg} mensagens...")
            deleted_msg = Message.objects.all().delete()[0]
            print(f"   ✅ {deleted_msg} mensagens deletadas")
            
            print(f"\n3️⃣ Deletando {total_conv} conversas...")
            deleted_conv = Conversation.objects.all().delete()[0]
            print(f"   ✅ {deleted_conv} conversas deletadas")
        
        print("\n" + "="*80)
        print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("="*80)
        
        # Mostrar estatísticas depois
        show_stats("DEPOIS DA LIMPEZA")
        
        print("\n" + "="*80)
        print("🎉 Banco de dados limpo!")
        print("   Agora você pode reconectar as instâncias WhatsApp")
        print("   e começar do zero com o sistema corrigido.")
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"\n❌ ERRO durante limpeza: {e}")
        print("   A transação foi revertida. Nenhum dado foi deletado.")
        raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Limpa todos os dados do chat (conversas, mensagens, anexos)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra estatísticas sem deletar nada'
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("\n🔍 MODO DRY-RUN - Apenas visualização")
        show_stats()
        print("\n💡 Execute sem --dry-run para deletar de verdade")
        return
    
    # Executar limpeza
    clear_all_chat_data()


if __name__ == '__main__':
    main()

