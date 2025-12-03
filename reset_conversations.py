"""
Script para resetar conversas e logs do sistema Flow Chat.
Remove todas as conversas, mensagens, anexos e logs relacionados.

USO:
    python reset_conversations.py                    # Modo interativo
    python reset_conversations.py --all              # Reseta TODOS os tenants
    python reset_conversations.py --tenant-id UUID   # Reseta apenas 1 tenant
"""
import os
import sys
import django
import argparse
from pathlib import Path

# Setup Django
current_dir = Path(__file__).parent
backend_dir = current_dir / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.core.cache import cache
from apps.tenancy.models import Tenant
from apps.chat.models import Conversation, Message, MessageAttachment


def list_tenants():
    """Lista todos os tenants disponíveis."""
    tenants = Tenant.objects.all().order_by('name')
    
    if not tenants.exists():
        print("❌ Nenhum tenant encontrado!")
        return []
    
    print("\n" + "="*70)
    print("📋 TENANTS DISPONÍVEIS:")
    print("="*70)
    
    for idx, tenant in enumerate(tenants, 1):
        conv_count = Conversation.objects.filter(tenant=tenant).count()
        msg_count = Message.objects.filter(conversation__tenant=tenant).count()
        
        print(f"\n{idx}. {tenant.name}")
        print(f"   ID: {tenant.id}")
        print(f"   Conversas: {conv_count}")
        print(f"   Mensagens: {msg_count}")
    
    print("="*70)
    
    return list(tenants)


def get_stats(tenant=None):
    """Retorna estatísticas de conversas e mensagens."""
    if tenant:
        conversations = Conversation.objects.filter(tenant=tenant)
        messages = Message.objects.filter(conversation__tenant=tenant)
        attachments = MessageAttachment.objects.filter(message__conversation__tenant=tenant)
    else:
        conversations = Conversation.objects.all()
        messages = Message.objects.all()
        attachments = MessageAttachment.objects.all()
    
    stats = {
        'conversations_total': conversations.count(),
        'conversations_groups': conversations.filter(conversation_type='group').count(),
        'conversations_individual': conversations.filter(conversation_type='individual').count(),
        'messages': messages.count(),
        'attachments': attachments.count(),
    }
    
    return stats


def reset_conversations(tenant=None, dry_run=False):
    """
    Reseta todas as conversas e dados relacionados.
    
    Args:
        tenant: Se fornecido, reseta apenas esse tenant. Se None, reseta tudo.
        dry_run: Se True, apenas mostra o que seria deletado sem deletar.
    """
    
    # Mostrar estatísticas antes
    print("\n" + "="*70)
    if tenant:
        print(f"📊 ESTATÍSTICAS - {tenant.name}")
    else:
        print("📊 ESTATÍSTICAS - TODOS OS TENANTS")
    print("="*70)
    
    stats = get_stats(tenant)
    
    print(f"\n📋 Conversas:")
    print(f"   Total: {stats['conversations_total']}")
    print(f"   Individuais: {stats['conversations_individual']}")
    print(f"   Grupos: {stats['conversations_groups']}")
    print(f"\n💬 Mensagens: {stats['messages']}")
    print(f"📎 Anexos: {stats['attachments']}")
    
    if stats['conversations_total'] == 0:
        print("\n✅ Nenhuma conversa para deletar!")
        return
    
    # Confirmação
    print("\n" + "="*70)
    if dry_run:
        print("🔍 MODO DRY-RUN - Apenas visualização, nada será deletado")
    else:
        print("⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!")
        print("   Todas as conversas, mensagens e anexos serão DELETADOS.")
    print("="*70)
    
    if not dry_run:
        confirm = input("\n❓ Digite 'CONFIRMAR' para prosseguir: ").strip()
        if confirm != 'CONFIRMAR':
            print("\n❌ Operação cancelada pelo usuário.")
            return
    
    # Deletar dados
    print("\n🗑️  Iniciando limpeza...")
    
    try:
        with transaction.atomic():
            # Filtros
            if tenant:
                conversations_qs = Conversation.objects.filter(tenant=tenant)
                messages_qs = Message.objects.filter(conversation__tenant=tenant)
                attachments_qs = MessageAttachment.objects.filter(
                    message__conversation__tenant=tenant
                )
            else:
                conversations_qs = Conversation.objects.all()
                messages_qs = Message.objects.all()
                attachments_qs = MessageAttachment.objects.all()
            
            if dry_run:
                print(f"\n✅ [DRY-RUN] Deletaria {attachments_qs.count()} anexos")
                print(f"✅ [DRY-RUN] Deletaria {messages_qs.count()} mensagens")
                print(f"✅ [DRY-RUN] Deletaria {conversations_qs.count()} conversas")
            else:
                # Deletar anexos primeiro
                deleted_attachments = attachments_qs.delete()[0]
                print(f"✅ Deletados {deleted_attachments} anexos")
                
                # Deletar mensagens
                deleted_messages = messages_qs.delete()[0]
                print(f"✅ Deletadas {deleted_messages} mensagens")
                
                # Deletar conversas
                deleted_conversations = conversations_qs.delete()[0]
                print(f"✅ Deletadas {deleted_conversations} conversas")
                
                # ✅ NOVO: Limpar cache do Redis relacionado a conversas
                print("\n4️⃣  Limpando cache do Redis...")
                try:
                    # Limpar cache de conversas (padrão Django cache)
                    cache.clear()
                    print("   ✅ Cache do Redis limpo")
                except Exception as e:
                    print(f"   ⚠️  Erro ao limpar cache (não crítico): {e}")
        
        print("\n" + "="*70)
        if dry_run:
            print("✅ DRY-RUN CONCLUÍDO - Nenhum dado foi deletado")
        else:
            print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("="*70)
        
        # Estatísticas após
        if not dry_run:
            stats_after = get_stats(tenant)
            print(f"\n📊 Conversas restantes: {stats_after['conversations_total']}")
            print(f"💬 Mensagens restantes: {stats_after['messages']}")
            print(f"📎 Anexos restantes: {stats_after['attachments']}")
    
    except Exception as e:
        print(f"\n❌ ERRO durante limpeza: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Reseta conversas e logs do sistema Flow Chat'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Reseta TODOS os tenants sem confirmação adicional'
    )
    parser.add_argument(
        '--tenant-id',
        type=str,
        help='ID do tenant para resetar (UUID)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra o que seria deletado, sem deletar'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🗑️  RESET DE CONVERSAS - Flow Chat")
    print("="*70)
    
    # Modo: resetar tenant específico
    if args.tenant_id:
        try:
            tenant = Tenant.objects.get(id=args.tenant_id)
            print(f"\n📌 Resetando apenas: {tenant.name}")
            reset_conversations(tenant, dry_run=args.dry_run)
        except Tenant.DoesNotExist:
            print(f"\n❌ Tenant não encontrado: {args.tenant_id}")
            sys.exit(1)
        return
    
    # Modo: resetar TODOS
    if args.all:
        print("\n⚠️  MODO: Resetar TODOS os tenants")
        reset_conversations(None, dry_run=args.dry_run)
        return
    
    # Modo interativo
    tenants = list_tenants()
    
    if not tenants:
        sys.exit(1)
    
    print("\n" + "="*70)
    print("OPÇÕES:")
    print("  1-N) Resetar apenas o tenant correspondente")
    print("  0)   Resetar TODOS os tenants")
    print("  q)   Cancelar")
    print("="*70)
    
    choice = input("\n❓ Escolha uma opção: ").strip().lower()
    
    if choice == 'q':
        print("\n❌ Operação cancelada.")
        return
    
    if choice == '0':
        print("\n⚠️  Resetando TODOS os tenants...")
        reset_conversations(None, dry_run=args.dry_run)
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(tenants):
            tenant = tenants[idx]
            print(f"\n📌 Resetando: {tenant.name}")
            reset_conversations(tenant, dry_run=args.dry_run)
        else:
            print("\n❌ Opção inválida!")
    except ValueError:
        print("\n❌ Opção inválida!")


if __name__ == '__main__':
    main()

