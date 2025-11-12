"""
Management command para iniciar o consumer RabbitMQ do chat.
Executar: python manage.py start_chat_rabbitmq_consumer

⚠️ IMPORTANTE: Este consumer processa apenas process_incoming_media (durabilidade crítica).
Outras tasks usam Redis (10x mais rápido).
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from apps.chat.tasks import start_chat_consumers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Inicia consumer RabbitMQ para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - chat_process_incoming_media: Processa mídia recebida (download + upload S3)
    
    ⚠️ Outras tasks (fetch_profile_pic, fetch_group_info) usam Redis.
    """
    
    help = 'Inicia consumer RabbitMQ para Flow Chat (process_incoming_media)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 [RABBITMQ CONSUMER] Iniciando Flow Chat RabbitMQ Consumer...'))
        self.stdout.write('   📌 Fila: chat_process_incoming_media')
        self.stdout.write('   📌 Task: process_incoming_media (download + upload S3)')
        self.stdout.write('')
        
        try:
            asyncio.run(start_chat_consumers())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ [RABBITMQ CONSUMER] Interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ [RABBITMQ CONSUMER] Erro: {e}'))
            logger.error(f"❌ [RABBITMQ CONSUMER] Erro fatal: {e}", exc_info=True)
            raise

