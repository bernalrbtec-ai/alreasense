"""
Management command para marcar logs Redis cleanup "running" travados como failed.
Pode ser agendado via cron (ex.: a cada 15 min).
"""
from django.core.management.base import BaseCommand

from apps.servicos.views import mark_stale_redis_cleanup_logs


class Command(BaseCommand):
    help = "Marca registros Redis cleanup com status 'running' antigos como 'failed' (stale)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=15,
            help="Considerar 'running' mais antigo que N minutos (default: 15).",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        self.stdout.write(
            self.style.WARNING(
                f"Marcando logs Redis cleanup 'running' com mais de {minutes} min como failed..."
            )
        )
        updated = mark_stale_redis_cleanup_logs(minutes=minutes)
        self.stdout.write(
            self.style.SUCCESS(f"Atualizados {updated} registro(s).")
        )
