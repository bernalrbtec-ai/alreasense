"""
Management command para iniciar o consumer Redis do chat.
Executar: python manage.py start_chat_consumer
"""
import asyncio
from django.core.management.base import BaseCommand
from apps.chat.redis_consumer import start_redis_consumers


class Command(BaseCommand):
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - send_message: Enviar mensagem via Evolution API
    - fetch_profile_pic: Buscar foto de perfil
    - fetch_group_info: Buscar info de grupo
    
    ⚠️ process_incoming_media ainda usa RabbitMQ (durabilidade crítica).
    """
    
    help = 'Inicia consumers Redis para Flow Chat (10x mais rápido que RabbitMQ)'
    
    def handle(self, *args, **options):
        """Executa consumer."""
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando consumer do Flow Chat (Redis)...'))
        self.stdout.write(self.style.SUCCESS('✅ Processando: send_message, fetch_profile_pic, fetch_group_info'))
        
        try:
            asyncio.run(start_redis_consumers())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Consumer interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))

