from django.core.management.base import BaseCommand
from apps.contacts.models import Contact
from django.db.models import Count


class Command(BaseCommand):
    help = 'Verifica contagem de contatos por estado'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Verificando contatos por estado...")
        self.stdout.write(f"📊 Total de contatos: {Contact.objects.count()}")

        # Contagem por estado
        state_counts = Contact.objects.values('state').annotate(count=Count('id')).order_by('-count')
        self.stdout.write(f"📊 Contagem por estado:")
        for item in state_counts:
            state_val = item['state'] if item['state'] else 'NULL'
            self.stdout.write(f"  • {state_val}: {item['count']} contatos")

        # Verificar especificamente DF
        df_count = Contact.objects.filter(state='DF').count()
        self.stdout.write(f"📍 DF especificamente: {df_count} contatos")

        # Mostrar alguns contatos DF
        df_contacts = Contact.objects.filter(state='DF')[:5]
        self.stdout.write(f"📍 Primeiros 5 contatos DF:")
        for contact in df_contacts:
            self.stdout.write(f"  • {contact.name} - {contact.phone} - {contact.state}")


