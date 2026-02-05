from datetime import datetime

from django.core.management.base import BaseCommand

from apps.ai.transcription_metrics import rebuild_transcription_metrics, resolve_date_range
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = "Rebuild AI transcription daily metrics for a date range."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            dest="tenant_id",
            help="UUID do tenant (opcional). Se omitido, processa todos.",
        )
        parser.add_argument(
            "--from",
            dest="created_from",
            help="Data inicial (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--to",
            dest="created_to",
            help="Data final (YYYY-MM-DD).",
        )

    def handle(self, *args, **options):
        created_from = self._parse_date(options.get("created_from"))
        created_to = self._parse_date(options.get("created_to"))
        start_date, end_date = resolve_date_range(created_from, created_to)

        tenant_id = options.get("tenant_id")
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("Nenhum tenant encontrado."))
            return

        for tenant in tenants:
            self.stdout.write(
                f"Rebuild metrics para tenant {tenant.id} ({tenant.name}) "
                f"de {start_date} até {end_date}"
            )
            rebuild_transcription_metrics(tenant, start_date, end_date)

        self.stdout.write(self.style.SUCCESS("Rebuild concluído."))

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
