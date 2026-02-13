"""
Agrega métricas diárias de mensagens e persiste em ChatMessageDailyMetric.
Rodar via cron (ex.: diariamente às 02:00) para o dia anterior.
"""
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tenancy.models import Tenant
from apps.chat.models import Conversation, ChatMessageDailyMetric
from apps.chat.message_metrics import aggregate_message_metrics_for_date


class Command(BaseCommand):
    help = "Agrega métricas diárias de mensagens (dia anterior ou range) e grava em ChatMessageDailyMetric."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="Data única a processar (YYYY-MM-DD). Default: ontem.",
        )
        parser.add_argument(
            "--from",
            dest="from_date",
            help="Data inicial (YYYY-MM-DD) para range.",
        )
        parser.add_argument(
            "--to",
            dest="to_date",
            help="Data final (YYYY-MM-DD) para range.",
        )
        parser.add_argument(
            "--tenant",
            dest="tenant_id",
            help="UUID do tenant (opcional). Se omitido, processa todos.",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id)
        else:
            tenants = Tenant.objects.all()

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("Nenhum tenant encontrado."))
            return

        single = options.get("date")
        from_date = self._parse_date(options.get("from_date"))
        to_date = self._parse_date(options.get("to_date"))

        if single:
            start_date = self._parse_date(single)
            if not start_date:
                self.stdout.write(self.style.ERROR("--date inválido. Use YYYY-MM-DD."))
                return
            end_date = start_date
        elif from_date and to_date:
            start_date = min(from_date, to_date)
            end_date = max(from_date, to_date)
        else:
            # Default: ontem
            yesterday = datetime.now().date() - timedelta(days=1)
            start_date = end_date = yesterday

        total_rows = 0
        for tenant in tenants:
            conv_qs = Conversation.objects.filter(tenant=tenant)
            current = start_date
            while current <= end_date:
                data = aggregate_message_metrics_for_date(conv_qs, current)
                with transaction.atomic():
                    ChatMessageDailyMetric.objects.update_or_create(
                        tenant=tenant,
                        date=current,
                        department=None,
                        defaults={
                            "total_count": data["total_count"],
                            "sent_count": data["sent_count"],
                            "received_count": data["received_count"],
                            "series_by_hour": data["series_by_hour"],
                            "avg_first_response_seconds": data["avg_first_response_seconds"],
                            "by_user": data["by_user"],
                        },
                    )
                total_rows += 1
                self.stdout.write(
                    f"  {tenant.name} {current}: total={data['total_count']} "
                    f"(sent={data['sent_count']}, recv={data['received_count']})"
                )
                current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Concluído: {total_rows} registro(s) atualizado(s)."))

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
