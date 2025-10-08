"""
Management command to seed initial data.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
from apps.experiments.models import PromptTemplate

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data for development'

    def handle(self, *args, **options):
        self.stdout.write('Seeding initial data...')

        # Create default tenant
        tenant, created = Tenant.objects.get_or_create(
            name='Demo Tenant',
            defaults={
                'plan': 'pro',
                'status': 'active'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created tenant: {tenant.name}')
            )
        else:
            self.stdout.write(f'Tenant already exists: {tenant.name}')

        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@evosense.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'tenant': tenant,
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created admin user: {admin_user.username}')
            )
        else:
            self.stdout.write(f'Admin user already exists: {admin_user.username}')

        # Create default prompt template
        prompt, created = PromptTemplate.objects.get_or_create(
            version='v1_default',
            defaults={
                'body': '''Analise a seguinte mensagem do WhatsApp e forneça:

1. Sentimento: um valor entre -1 (muito negativo) e 1 (muito positivo)
2. Emoção: a emoção principal detectada (positivo, negativo, neutro, feliz, triste, irritado, ansioso, calmo, confuso, surpreso)
3. Satisfação: um valor entre 0 (muito insatisfeito) e 100 (muito satisfeito)
4. Tom: o tom da mensagem (cordial, formal, informal, agressivo, passivo, assertivo)
5. Resumo: um resumo conciso da mensagem em até 200 caracteres

Mensagem: "{message}"

Responda apenas com um JSON válido no formato:
{{
    "sentiment": 0.72,
    "emotion": "positivo",
    "satisfaction": 85,
    "tone": "cordial",
    "summary": "Cliente satisfeito com o atendimento"
}}''',
                'description': 'Template padrão para análise de sentimento',
                'is_active': True,
                'created_by': 'system'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created prompt template: {prompt.version}')
            )
        else:
            self.stdout.write(f'Prompt template already exists: {prompt.version}')

        self.stdout.write(
            self.style.SUCCESS('Initial data seeded successfully!')
        )
        self.stdout.write('Login credentials:')
        self.stdout.write('Username: admin')
        self.stdout.write('Password: admin123')
