"""
Cria/atualiza o produto ALREA Chat.

Chat é o produto "pai": os limites (instâncias e usuários) vêm sempre dele.
ALREA Chat inclui: Chat, Respostas rápidas, Agenda, Contatos e Instâncias WhatsApp.
Limitadores no plano (PlanProduct do Chat): instâncias (limit_value/limit_unit) e usuários (limit_value_secondary/limit_unit_secondary).

Uso: python manage.py create_chat_product
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.billing.models import Product


class Command(BaseCommand):
    help = 'Cria ou atualiza o produto ALREA Chat (Chat, Respostas rápidas, Agenda, Contatos, Instâncias WhatsApp) com limitadores de instâncias e usuários'

    def handle(self, *args, **options):
        self.stdout.write('Criando/atualizando produto ALREA Chat...')
        description = (
            'Atendimento completo: Chat, Respostas rápidas, Agenda (horários e tarefas), Contatos e Instâncias WhatsApp. '
            'Limitadores: número de instâncias e número de usuários por plano.'
        )
        chat_product, created = Product.objects.get_or_create(
            slug='chat',
            defaults={
                'name': 'ALREA Chat',
                'description': description,
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': None,
                'icon': '💬',
                'color': '#0EA5E9',
            }
        )
        if not created:
            chat_product.name = 'ALREA Chat'
            chat_product.description = description
            chat_product.is_active = True
            chat_product.requires_ui_access = True
            chat_product.icon = '💬'
            chat_product.color = '#0EA5E9'
            chat_product.save()
            self.stdout.write(self.style.SUCCESS('  Produto ALREA Chat atualizado'))
        else:
            self.stdout.write(self.style.SUCCESS('  Produto ALREA Chat criado'))
        self.stdout.write('')
        self.stdout.write('Próximos passos:')
        self.stdout.write('  1. Na tela Planos (Admin), adicione o produto "ALREA Chat" aos planos desejados.')
        self.stdout.write('  2. Para cada plano, defina:')
        self.stdout.write('     - Limite de instâncias (limit_value / limit_unit = "instâncias")')
        self.stdout.write('     - Limite de usuários (limit_value_secondary / limit_unit_secondary = "usuários")')
        self.stdout.write('  3. Ao atribuir o plano a um tenant, o sistema ativará o produto "chat" e aplicará os limites.')
