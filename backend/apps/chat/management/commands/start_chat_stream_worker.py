"""
Management command para iniciar workers baseados em Redis Streams.
Executar: python manage.py start_chat_stream_worker
"""
import asyncio
from typing import Optional

from django.core.management.base import BaseCommand

from apps.chat.stream_consumer import start_stream_workers


class Command(BaseCommand):
    """
    Inicia workers que consomem as streams do chat:
    - send_message (Redis Streams)
    - mark_as_read (Redis Streams)
    """

    help = 'Inicia workers do Flow Chat baseados em Redis Streams (envio e read receipts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--send-workers',
            type=int,
            default=3,
            help='Quantidade de workers para envio de mensagens (padrão: 3)'
        )
        parser.add_argument(
            '--mark-workers',
            type=int,
            default=2,
            help='Quantidade de workers para mark_as_read (padrão: 2)'
        )
        parser.add_argument(
            '--consumer-prefix',
            type=str,
            default=None,
            help='Prefixo personalizado para identificar consumidores no grupo'
        )
        parser.add_argument(
            '--queues',
            nargs='+',
            help='Filtrar filas (send, mark). Ex: --queues send'
        )

    def handle(
        self,
        *args,
        send_workers: int,
        mark_workers: int,
        consumer_prefix: Optional[str],
        queues: Optional[list[str]] = None,
        **options
    ):
        """Executa os workers de streams."""
        try:
            asyncio.run(
                start_stream_workers(
                    send_workers=send_workers,
                    mark_workers=mark_workers,
                    consumer_prefix=consumer_prefix,
                    queue_filters=queues,
                )
            )
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n⚠️ Workers interrompidos pelo usuário'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {exc}'))

