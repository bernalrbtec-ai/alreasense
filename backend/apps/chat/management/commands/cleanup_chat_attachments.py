"""
Management command para limpar anexos locais expirados.
Executar via cron: python manage.py cleanup_chat_attachments
"""
from django.core.management.base import BaseCommand
from apps.chat.utils.storage import cleanup_expired_local_files


class Command(BaseCommand):
    """
    Limpa anexos locais expirados (>7 dias).
    Remove arquivos do filesystem e registros do banco.
    """
    
    help = 'Remove anexos locais expirados do chat'
    
    def handle(self, *args, **options):
        """Executa limpeza."""
        self.stdout.write(self.style.WARNING('🧹 Iniciando limpeza de anexos expirados...'))
        
        deleted_count = cleanup_expired_local_files()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Limpeza concluída: {deleted_count} arquivos removidos')
        )

