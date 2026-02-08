"""
Management command para fechar conversas no Inbox após X minutos sem interação.
Executar: python manage.py close_inbox_idle_conversations [--once]

Para cada tenant com secretária habilitada e inbox_idle_minutes > 0:
- Busca conversas no Inbox (department_id null, status pending/open)
- last_message_at anterior a (agora - inbox_idle_minutes)
- Envia mensagem de despedida ao cliente e marca conversa como closed.

Agendar via cron (ex.: a cada 5–15 min):
  */10 * * * * cd /app && python manage.py close_inbox_idle_conversations --once
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.ai.models import TenantAiSettings, TenantSecretaryProfile
from apps.chat.models import Conversation, Message

logger = logging.getLogger(__name__)

DEFAULT_GOODBYE_MESSAGE = (
    "Não recebemos resposta nos últimos {minutes} minutos. Encerramos por ora. "
    "Quando quiser, envie uma nova mensagem."
)


class Command(BaseCommand):
    help = "Fecha conversas no Inbox após tempo configurado sem interação (inbox_idle_minutes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Executa uma vez e sai (para cron).",
        )

    def handle(self, *args, **options):
        run_once = options["once"]
        now = timezone.now()
        closed_count = 0

        # Tenants com secretária habilitada e inbox_idle_minutes > 0
        profiles = TenantSecretaryProfile.objects.filter(
            inbox_idle_minutes__gt=0,
        ).select_related("tenant")
        tenant_ids_with_minutes = {
            p.tenant_id: p.inbox_idle_minutes
            for p in profiles
            if getattr(p, "inbox_idle_minutes", 0) and p.inbox_idle_minutes <= 1440
        }
        if not tenant_ids_with_minutes:
            self.stdout.write("Nenhum tenant com inbox_idle_minutes > 0.")
            return

        # Só tenants que têm secretary_enabled
        enabled_tenant_ids = set(
            TenantAiSettings.objects.filter(
                secretary_enabled=True,
                tenant_id__in=tenant_ids_with_minutes.keys(),
            ).values_list("tenant_id", flat=True)
        )
        tenant_minutes = {
            tid: tenant_ids_with_minutes[tid]
            for tid in enabled_tenant_ids
            if tid in tenant_ids_with_minutes
        }
        if not tenant_minutes:
            self.stdout.write("Nenhum tenant com secretária habilitada e inbox_idle_minutes > 0.")
            return

        for tenant_id, minutes in tenant_minutes.items():
            cutoff = now - timedelta(minutes=minutes)
            # Conversas no Inbox, abertas/pendentes, última mensagem antes do cutoff
            qs = Conversation.objects.filter(
                tenant_id=tenant_id,
                department_id__isnull=True,
                status__in=("pending", "open"),
            ).filter(
                Q(last_message_at__lt=cutoff) | Q(last_message_at__isnull=True, created_at__lt=cutoff)
            )
            for conv in qs:
                try:
                    goodbye = DEFAULT_GOODBYE_MESSAGE.format(minutes=minutes)
                    msg = Message.objects.create(
                        conversation=conv,
                        sender=None,
                        sender_name="Sistema",
                        content=goodbye,
                        direction="outgoing",
                        status="pending",
                        is_internal=False,
                    )
                    from apps.chat.tasks import send_message_to_evolution

                    send_message_to_evolution.delay(str(msg.id))
                    conv.status = "closed"
                    conv.save(update_fields=["status"])
                    closed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Fechada conversa {conv.id} (tenant={tenant_id})"
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Erro ao fechar conversa {conv.id}: {e}")
                    )
                    logger.exception("close_inbox_idle: conversation %s", conv.id)

        self.stdout.write(self.style.SUCCESS(f"Total de conversas fechadas: {closed_count}"))
