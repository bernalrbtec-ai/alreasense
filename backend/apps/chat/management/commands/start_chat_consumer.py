"""
Management command para iniciar o consumer Redis do chat.
Executar: python manage.py start_chat_consumer
"""
import asyncio
from django.core.management.base import BaseCommand
from apps.chat.redis_consumer import start_redis_consumers, QUEUE_ALIASES


class Command(BaseCommand):
    """
    Inicia consumers Redis para processar filas do chat.
    Roda em loop infinito processando mensagens.
    
    Filas processadas:
    - fetch_profile_pic: Buscar foto de perfil
    - fetch_group_info: Buscar info de grupo
    
    ⚠️ process_incoming_media ainda usa RabbitMQ (durabilidade crítica).
    """
    
    help = 'Inicia consumers Redis para Flow Chat (10x mais rápido que RabbitMQ)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--queues',
            nargs='+',
            help='Lista de filas para processar (fetch_profile_pic, fetch_group_info)'
        )
    
    def handle(self, *args, **options):
        """Executa consumer."""
        requested_queues = options.get('queues') or []
        queue_filters = None

        if requested_queues:
            normalized = set()
            invalid = []
            for queue in requested_queues:
                key = (queue or '').strip().lower()
                if key in QUEUE_ALIASES:
                    normalized.add(QUEUE_ALIASES[key])
                elif key:
                    invalid.append(queue)
            if invalid:
                self.stdout.write(self.style.WARNING(f'⚠️ Filas desconhecidas ignoradas: {", ".join(invalid)}'))
            if normalized:
                queue_filters = normalized
                self.stdout.write(self.style.SUCCESS(
                    f'🚀 Iniciando consumer do Flow Chat (Redis) filtrado: {", ".join(sorted(normalized))}'
                ))
            else:
                self.stdout.write(self.style.WARNING('⚠️ Nenhuma fila válida informada, processando todas.'))
        else:
            self.stdout.write(self.style.SUCCESS('🚀 Iniciando consumer do Flow Chat (Redis)...'))
            self.stdout.write(self.style.SUCCESS('✅ Processando: fetch_profile_pic, fetch_group_info'))
        
        try:
            asyncio.run(start_redis_consumers(queue_filters))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Consumer interrompido pelo usuário'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))

