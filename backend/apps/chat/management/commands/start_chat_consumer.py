"""
Management command para iniciar o consumer RabbitMQ do chat.
Executar: python manage.py start_chat_consumer
"""
import asyncio
from django.core.management.base import BaseCommand
from apps.chat.tasks import start_chat_consumers


class Command(BaseCommand):
    """
    Inicia consumers RabbitMQ para processar filas do chat.
    Roda em loop infinito processando mensagens.
    """
    
    help = 'Inicia consumers RabbitMQ para Flow Chat'
    
    def handle(self, *args, **options):
        """Executa consumer."""
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando consumer do Flow Chat...'))
        
        try:
            asyncio.run(start_chat_consumers())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Consumer interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))

