"""
Comando para limpar dados de chat de um tenant específico.

USO:
    python manage.py cleanup_tenant_chat --tenant-id <uuid>
    
    OU para limpar apenas anexos:
    python manage.py cleanup_tenant_chat --tenant-id <uuid> --only-attachments
    
    OU para limpar apenas mensagens:
    python manage.py cleanup_tenant_chat --tenant-id <uuid> --only-messages

AVISO: Este comando é DESTRUTIVO e não pode ser desfeito!
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.chat.models import Message, MessageAttachment, Conversation
from apps.chat.utils.s3 import S3Manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Limpa dados de chat de um tenant específico'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            required=True,
            help='UUID do tenant a ser limpo'
        )
        parser.add_argument(
            '--only-attachments',
            action='store_true',
            help='Limpar apenas anexos (mantém mensagens e conversas)'
        )
        parser.add_argument(
            '--only-messages',
            action='store_true',
            help='Limpar apenas mensagens (mantém conversas)'
        )
        parser.add_argument(
            '--keep-conversations',
            action='store_true',
            help='Manter conversas (apenas limpar mensagens/anexos)'
        )
        parser.add_argument(
            '--clean-s3',
            action='store_true',
            help='Também deletar arquivos do S3/MinIO'
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Pular confirmação (use com cuidado!)'
        )

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        only_attachments = options['only_attachments']
        only_messages = options['only_messages']
        keep_conversations = options['keep_conversations']
        clean_s3 = options['clean_s3']
        skip_confirmation = options['yes']

        self.stdout.write(self.style.WARNING('\n' + '='*70))
        self.stdout.write(self.style.WARNING('⚠️  LIMPEZA DE DADOS DO TENANT'))
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(f'\nTenant ID: {tenant_id}\n')

        # Verificar se tenant existe
        from apps.tenancy.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            self.stdout.write(f'Tenant: {tenant.name}')
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Tenant não encontrado: {tenant_id}'))
            return

        # Contar registros
        attachments_count = MessageAttachment.objects.filter(tenant_id=tenant_id).count()
        messages_count = Message.objects.filter(conversation__tenant_id=tenant_id).count()
        conversations_count = Conversation.objects.filter(tenant_id=tenant_id).count()

        self.stdout.write(f'\n📊 Estatísticas atuais:')
        self.stdout.write(f'   • Conversas: {conversations_count}')
        self.stdout.write(f'   • Mensagens: {messages_count}')
        self.stdout.write(f'   • Anexos: {attachments_count}')

        # Determinar o que será deletado
        delete_attachments = only_attachments or (not only_messages)
        delete_messages = only_messages or (not only_attachments)
        delete_conversations = not keep_conversations and not only_attachments and not only_messages

        self.stdout.write(f'\n🗑️  Será deletado:')
        if delete_conversations:
            self.stdout.write(self.style.WARNING(f'   ⚠️  TODAS as conversas ({conversations_count})'))
        if delete_messages:
            self.stdout.write(self.style.WARNING(f'   ⚠️  TODAS as mensagens ({messages_count})'))
        if delete_attachments:
            self.stdout.write(self.style.WARNING(f'   ⚠️  TODOS os anexos ({attachments_count})'))
            if clean_s3:
                self.stdout.write(self.style.WARNING('   ⚠️  Arquivos no S3 também serão deletados!'))

        # Confirmação
        if not skip_confirmation:
            self.stdout.write(self.style.ERROR('\n⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!'))
            confirm = input('\nDigite "SIM" para confirmar: ')
            if confirm != 'SIM':
                self.stdout.write(self.style.SUCCESS('❌ Operação cancelada.'))
                return

        # Executar limpeza
        self.stdout.write(self.style.WARNING('\n🔄 Iniciando limpeza...\n'))

        with transaction.atomic():
            deleted_attachments = 0
            deleted_messages = 0
            deleted_conversations = 0
            deleted_s3_files = 0

            # 1. Deletar anexos
            if delete_attachments:
                self.stdout.write('📎 Deletando anexos...')
                attachments = MessageAttachment.objects.filter(tenant_id=tenant_id)
                
                if clean_s3:
                    s3_manager = S3Manager()
                    for attachment in attachments:
                        if attachment.file_path and attachment.storage_type == 's3':
                            try:
                                success, msg = s3_manager.delete_from_s3(attachment.file_path)
                                if success:
                                    deleted_s3_files += 1
                                    logger.info(f'✅ [CLEANUP] Arquivo deletado do S3: {attachment.file_path}')
                                else:
                                    logger.warning(f'⚠️ [CLEANUP] Erro ao deletar do S3: {attachment.file_path} - {msg}')
                            except Exception as e:
                                logger.error(f'❌ [CLEANUP] Erro ao deletar do S3: {attachment.file_path} - {e}')

                deleted_attachments = attachments.count()
                attachments.delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {deleted_attachments} anexos deletados'))
                if clean_s3:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ {deleted_s3_files} arquivos deletados do S3'))

            # 2. Deletar mensagens
            if delete_messages:
                self.stdout.write('💬 Deletando mensagens...')
                messages = Message.objects.filter(conversation__tenant_id=tenant_id)
                deleted_messages = messages.count()
                messages.delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {deleted_messages} mensagens deletadas'))

            # 3. Deletar conversas (se não mantiver)
            if delete_conversations:
                self.stdout.write('💬 Deletando conversas...')
                conversations = Conversation.objects.filter(tenant_id=tenant_id)
                deleted_conversations = conversations.count()
                conversations.delete()
                self.stdout.write(self.style.SUCCESS(f'   ✅ {deleted_conversations} conversas deletadas'))

        # Resumo
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ LIMPEZA CONCLUÍDA!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'\n📊 Resumo:')
        if delete_conversations:
            self.stdout.write(f'   • Conversas deletadas: {deleted_conversations}')
        if delete_messages:
            self.stdout.write(f'   • Mensagens deletadas: {deleted_messages}')
        if delete_attachments:
            self.stdout.write(f'   • Anexos deletados: {deleted_attachments}')
            if clean_s3:
                self.stdout.write(f'   • Arquivos S3 deletados: {deleted_s3_files}')
        self.stdout.write('\n')

