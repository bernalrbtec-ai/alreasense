from django.core.management.base import BaseCommand
from apps.contacts.models import Contact
from apps.contacts.utils import get_state_from_phone
from django.db.models import Count


class Command(BaseCommand):
    help = 'Corrige estados dos contatos baseado no DDD do telefone'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Corrigindo estados dos contatos...")

        # Buscar contatos sem estado
        contacts_without_state = Contact.objects.filter(state__isnull=True)
        self.stdout.write(f"📊 Contatos sem estado: {contacts_without_state.count()}")

        # Buscar contatos com estado vazio
        contacts_empty_state = Contact.objects.filter(state='')
        self.stdout.write(f"📊 Contatos com estado vazio: {contacts_empty_state.count()}")

        total_to_fix = contacts_without_state.count() + contacts_empty_state.count()
        self.stdout.write(f"📊 Total a corrigir: {total_to_fix}")

        if total_to_fix == 0:
            self.stdout.write("✅ Todos os contatos já têm estado definido!")
            return

        fixed_count = 0

        # Corrigir contatos sem estado
        for contact in contacts_without_state:
            if contact.phone:
                state = get_state_from_phone(contact.phone)
                if state:
                    contact.state = state
                    contact.save(update_fields=['state'])
                    fixed_count += 1
                    self.stdout.write(f"  ✅ {contact.name} ({contact.phone}) → {state}")

        # Corrigir contatos com estado vazio
        for contact in contacts_empty_state:
            if contact.phone:
                state = get_state_from_phone(contact.phone)
                if state:
                    contact.state = state
                    contact.save(update_fields=['state'])
                    fixed_count += 1
                    self.stdout.write(f"  ✅ {contact.name} ({contact.phone}) → {state}")

        self.stdout.write(f"\n🎉 Corrigidos {fixed_count} contatos!")

        # Mostrar estatísticas finais
        self.stdout.write("\n📊 Estatísticas finais:")
        state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
        for item in state_counts:
            state_val = item['state'] if item['state'] else 'NULL'
            self.stdout.write(f"  • {state_val}: {item['count']} contatos")



