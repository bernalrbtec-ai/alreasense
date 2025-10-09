from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.campaigns.models import Holiday
from apps.contacts.models import Contact
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = 'Seed de dados iniciais para campanhas'
    
    def handle(self, *args, **options):
        self.stdout.write('🌱 Seed de Campanhas...')
        
        # Seed de feriados nacionais 2025
        holidays_2025 = [
            ('2025-01-01', 'Ano Novo'),
            ('2025-02-17', 'Carnaval'),
            ('2025-02-18', 'Carnaval'),
            ('2025-02-19', 'Carnaval'),
            ('2025-04-18', 'Sexta-feira Santa'),
            ('2025-04-21', 'Tiradentes'),
            ('2025-05-01', 'Dia do Trabalho'),
            ('2025-06-19', 'Corpus Christi'),
            ('2025-09-07', 'Independência do Brasil'),
            ('2025-10-12', 'Nossa Senhora Aparecida'),
            ('2025-11-02', 'Finados'),
            ('2025-11-15', 'Proclamação da República'),
            ('2025-11-20', 'Consciência Negra'),
            ('2025-12-25', 'Natal'),
        ]
        
        created_holidays = 0
        for date, name in holidays_2025:
            holiday, created = Holiday.objects.get_or_create(
                date=date,
                tenant=None,
                defaults={
                    'name': name,
                    'is_national': True,
                    'is_active': True
                }
            )
            if created:
                created_holidays += 1
                self.stdout.write(f'  ✓ Feriado: {name} ({date})')
        
        self.stdout.write(self.style.SUCCESS(f'✅ {created_holidays} feriados criados'))
        
        # Criar contato de teste para você
        try:
            tenant = Tenant.objects.first()
            if tenant:
                contact, created = Contact.objects.get_or_create(
                    tenant=tenant,
                    phone='+5517991253112',
                    defaults={
                        'name': 'Paulo (Teste ALREA)',
                        'quem_indicou': 'Sistema ALREA',
                        'notes': 'Contato de teste para validação do sistema de campanhas',
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS('✅ Contato de teste criado: Paulo (+5517991253112)'))
                else:
                    self.stdout.write('  ℹ️  Contato de teste já existe')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Não foi possível criar contato de teste: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Seed concluído!'))

