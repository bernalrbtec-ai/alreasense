"""
Verifica se as instâncias WhatsApp estão com instance_name/evolution_instance_name
alinhados ao que a Evolution envia no webhook (campo `instance`).

Uso:
  python manage.py check_webhook_instance
      Lista todas as instâncias e seus identificadores.

  python manage.py check_webhook_instance 01371b7f-197e-4da9-8c91-4409d0321c44
      Verifica se esse valor (o que a Evolution envia) encontra alguma instância.
"""
from django.core.management.base import BaseCommand
from apps.notifications.models import WhatsAppInstance
from apps.notifications.webhook_resolution import resolve_wa_instance_by_webhook_id


class Command(BaseCommand):
    help = 'Lista instâncias WhatsApp e verifica se o identificador do webhook (Evolution) encontra alguma.'

    def add_arguments(self, parser):
        parser.add_argument(
            'instance_from_webhook',
            nargs='?',
            type=str,
            default=None,
            help='Valor do campo "instance" que a Evolution envia no webhook (ex.: UUID)',
        )

    def handle(self, *args, **options):
        instance_from_webhook = options.get('instance_from_webhook')
        if instance_from_webhook:
            instance_from_webhook = str(instance_from_webhook).strip()

        # Listar todas as instâncias
        instances = WhatsAppInstance.objects.select_related('tenant').order_by('tenant__name', 'friendly_name')
        self.stdout.write('')
        self.stdout.write('=== Instâncias WhatsApp (banco) ===')
        self.stdout.write('')
        for wi in instances:
            tenant_name = wi.tenant.name if wi.tenant else '(sem tenant)'
            in_ev = (wi.instance_name or '').strip()
            ev_ev = (wi.evolution_instance_name or '').strip()
            self.stdout.write(
                f"  {wi.friendly_name!r}  |  tenant={tenant_name}  |  instance_name={in_ev!r}  |  evolution_instance_name={ev_ev!r}  |  is_active={wi.is_active}"
            )
        self.stdout.write('')

        if instance_from_webhook:
            self.stdout.write(f'=== Teste: webhook envia instance = {instance_from_webhook!r} ===')
            found = resolve_wa_instance_by_webhook_id(instance_from_webhook)
            if found:
                self.stdout.write(self.style.SUCCESS(
                    f'  OK: Encontrada instância "{found.friendly_name}" (tenant={found.tenant.name if found.tenant else "N/A"})'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    '  NENHUMA instância encontrada. Cadastre esse valor em instance_name ou evolution_instance_name.'
                ))
            self.stdout.write('')
        else:
            self.stdout.write(
                'Para testar o valor que a Evolution envia, use: python manage.py check_webhook_instance <valor_instance>'
            )
            self.stdout.write('')
            self.stdout.write('Tabela no banco: notifications_whatsapp_instance')
            self.stdout.write('')
