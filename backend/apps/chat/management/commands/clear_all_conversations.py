"""
Comando Django para zerar todas as conversas do sistema
⚠️ ATENÇÃO: Esta operação é IRREVERSÍVEL!
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Zera todas as conversas do sistema (IRREVERSÍVEL)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='UUID do tenant para zerar apenas conversas de um tenant específico',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma a operação sem pedir confirmação interativa',
        )
        parser.add_argument(
            '--keep-messages',
            action='store_true',
            help='Mantém mensagens, apenas deleta conversas',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        confirm = options.get('confirm', False)
        keep_messages = options.get('keep_messages', False)

        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('⚠️  ZERAR TODAS AS CONVERSAS'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        # Buscar conversas
        if tenant_id:
            from apps.tenancy.models import Tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                conversations = Conversation.objects.filter(tenant=tenant)
                self.stdout.write(f"📋 Tenant: {tenant.name}")
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Tenant não encontrado: {tenant_id}"))
                return
        else:
            conversations = Conversation.objects.all()
            self.stdout.write("📋 Todos os tenants")
        
        total_conversations = conversations.count()
        
        if total_conversations == 0:
            self.stdout.write(self.style.SUCCESS("✅ Nenhuma conversa encontrada!"))
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
        
        self.stdout.write(f"\n📊 Estatísticas:")
        self.stdout.write(f"   📋 Conversas: {total_conversations}")
        if not keep_messages:
            self.stdout.write(f"   💬 Mensagens: {total_messages}")
            self.stdout.write(f"   📎 Anexos: {total_attachments}")
            self.stdout.write(f"   👍 Reações: {total_reactions}")
        
        self.stdout.write(self.style.WARNING('\n⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!'))
        self.stdout.write(self.style.WARNING('   Todas as conversas serão deletadas permanentemente.'))
        if not keep_messages:
            self.stdout.write(self.style.WARNING('   Todas as mensagens, anexos e reações também serão deletados.'))
        
        # Confirmação
        if not confirm:
            self.stdout.write(self.style.WARNING('\n❓ Deseja continuar? (digite "SIM" para confirmar):'))
            user_input = input().strip()
            if user_input != 'SIM':
                self.stdout.write(self.style.SUCCESS('❌ Operação cancelada.'))
                return
        
        # Executar deleção
        self.stdout.write(self.style.WARNING('\n🗑️  Deletando...'))
        
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
                
                self.stdout.write(self.style.SUCCESS(f'\n✅ Deleção concluída!'))
                self.stdout.write(f"   📋 Conversas deletadas: {deleted_conversations}")
                if not keep_messages:
                    self.stdout.write(f"   💬 Mensagens deletadas: {deleted_messages}")
                    self.stdout.write(f"   📎 Anexos deletados: {deleted_attachments}")
                    self.stdout.write(f"   👍 Reações deletadas: {deleted_reactions}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Erro ao deletar: {e}'))
            import traceback
            traceback.print_exc()
            raise

