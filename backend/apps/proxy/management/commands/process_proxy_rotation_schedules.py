"""
Processa agendamentos de rotação de proxy cuja next_run_at já passou.

Configure no cron (ex. a cada minuto):
    python manage.py process_proxy_rotation_schedules

Usa as mesmas credenciais Webshare/Evolution da app (settings).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.proxy.models import ProxyRotationSchedule
from apps.proxy.services import run_proxy_rotation


class Command(BaseCommand):
    help = "Executa rotações de proxy agendadas (next_run_at <= agora)."

    def handle(self, *args, **options):
        now = timezone.now()
        due = (
            ProxyRotationSchedule.objects.filter(
                is_active=True,
                next_run_at__isnull=False,
                next_run_at__lte=now,
            )
            .order_by("next_run_at")
        )

        processed = 0
        skipped_lock = 0

        for schedule in due:
            log, err = run_proxy_rotation(
                triggered_by="scheduled",
                user=None,
                strategy_override=schedule.strategy,
            )
            if err and not log:
                if err and "em execução" in err:
                    skipped_lock += 1
                    self.stdout.write(self.style.WARNING(f"Agendamento #{schedule.pk}: {err}"))
                    break
                self.stdout.write(self.style.ERROR(f"Agendamento #{schedule.pk}: {err}"))
                continue

            if log:
                schedule.last_run_at = timezone.now()
                schedule.next_run_at = timezone.now() + timedelta(
                    minutes=schedule.interval_minutes
                )
                schedule.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
                processed += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Agendamento #{schedule.pk} ({schedule.name or 'sem nome'}): "
                        f"log #{log.id} status={log.status}"
                    )
                )
