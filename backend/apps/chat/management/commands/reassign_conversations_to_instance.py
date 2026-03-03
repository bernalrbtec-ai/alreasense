"""
Reatribui conversas "órfãs" (instance_name de instância removida) à instância ativa do tenant.

Útil quando você removeu a única instância de um tenant e conectou outra: as conversas
continuam com instance_name da instância antiga. Este comando atualiza instance_name e
instance_friendly_name para a nova instância.

Uso:
  python manage.py reassign_conversations_to_instance --tenant=meu-tenant
  python manage.py reassign_conversations_to_instance --tenant=meu-tenant --instance=<UUID ou instance_name>
  python manage.py reassign_conversations_to_instance --tenant=meu-tenant --dry-run
"""
import logging
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.chat.models import Conversation
from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reatribui conversas órfãs (instância removida) à instância ativa do tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            required=True,
            help="Slug ou ID do tenant.",
        )
        parser.add_argument(
            "--instance",
            type=str,
            default=None,
            help="ID (UUID) ou instance_name da WhatsAppInstance alvo. Se omitido e o tenant tiver só uma instância ativa, usa ela.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista o que seria atualizado, sem alterar o banco.",
        )

    def handle(self, *args, **options):
        tenant_slug_or_id = options["tenant"].strip()
        instance_arg = options.get("instance")
        dry_run = options.get("dry_run", False)

        # Resolver tenant
        tenant = None
        if tenant_slug_or_id:
            tenant = Tenant.objects.filter(slug=tenant_slug_or_id).first()
            if not tenant:
                try:
                    tenant = Tenant.objects.get(id=tenant_slug_or_id)
                except (ValueError, Tenant.DoesNotExist):
                    pass
        if not tenant:
            self.stderr.write(self.style.ERROR(f"Tenant não encontrado: {tenant_slug_or_id}"))
            return

        # Resolver instância alvo
        wa = None
        if instance_arg:
            wa = WhatsAppInstance.objects.filter(
                tenant=tenant,
                is_active=True,
            ).filter(
                Q(id=instance_arg) | Q(instance_name=instance_arg) | Q(evolution_instance_name=instance_arg)
            ).first()
            if not wa:
                self.stderr.write(self.style.ERROR(f"Instância não encontrada no tenant: {instance_arg}"))
                return
        else:
            active = list(WhatsAppInstance.objects.filter(tenant=tenant, is_active=True))
            if len(active) == 0:
                self.stderr.write(self.style.ERROR("Tenant não tem nenhuma instância ativa."))
                return
            if len(active) > 1:
                self.stderr.write(
                    self.style.ERROR(
                        "Tenant tem mais de uma instância ativa. Use --instance=<id ou instance_name>."
                    )
                )
                return
            wa = active[0]

        self.stdout.write(
            f"Tenant: {tenant.name} | Instância alvo: {wa.friendly_name or wa.instance_name} ({wa.instance_name})"
        )

        # Um único query para todos os identificadores válidos (evita 3 round-trips)
        valid_instance_names = set()
        valid_evolution_names = set()
        valid_phone_number_ids = set()
        for row in WhatsAppInstance.objects.filter(tenant=tenant, is_active=True).values_list(
            "instance_name", "evolution_instance_name", "phone_number_id"
        ):
            if row[0]:
                valid_instance_names.add(str(row[0]).strip())
            if row[1]:
                valid_evolution_names.add(str(row[1]).strip())
            if row[2]:
                valid_phone_number_ids.add(str(row[2]).strip())

        def is_orphan(conv):
            iname = (conv.instance_name or "").strip()
            if not iname:
                return False
            if iname in valid_instance_names or iname in valid_evolution_names:
                return False
            if iname.isdigit() and iname in valid_phone_number_ids:
                return False
            return True

        orphans = [
            c
            for c in Conversation.objects.filter(tenant=tenant).only(
                "id", "instance_name", "instance_friendly_name"
            )
            if is_orphan(c)
        ]

        if not orphans:
            self.stdout.write(self.style.SUCCESS("Nenhuma conversa órfã encontrada."))
            return

        self.stdout.write(f"Conversas órfãs a atualizar: {len(orphans)}")
        if dry_run:
            for c in orphans[:10]:
                self.stdout.write(f"  - {c.id} instance_name={c.instance_name!r}")
            if len(orphans) > 10:
                self.stdout.write(f"  ... e mais {len(orphans) - 10}")
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração feita."))
            return

        friendly_value = (wa.friendly_name or "").strip() or wa.instance_name
        for c in orphans:
            c.instance_name = wa.instance_name
            c.instance_friendly_name = friendly_value
        Conversation.objects.bulk_update(
            orphans, ["instance_name", "instance_friendly_name"], batch_size=500
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Atualizadas {len(orphans)} conversas para a instância {wa.friendly_name or wa.instance_name}."
            )
        )
