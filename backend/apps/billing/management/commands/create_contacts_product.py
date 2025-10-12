from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan


class Command(BaseCommand):
    help = 'Cria o produto Contatos para gestão de leads e contatos'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando produto Contatos...")
        
        # Produto Contatos
        contacts_product, created = Product.objects.get_or_create(
            slug='contacts',
            defaults={
                'name': 'Contatos',
                'description': 'Gestão avançada de contatos e leads com tags, segmentação e automação de listas',
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': 19.90,  # Pode ser addon
                'icon': '👥',
                'color': '#3B82F6'  # Azul
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto Contatos criado: {contacts_product.name}")
        else:
            self.stdout.write(f"  ℹ️ Produto Contatos já existe: {contacts_product.name}")
        
        # Criar planos específicos para Contatos
        self.create_contacts_plans(contacts_product)
        
        self.stdout.write("✅ Produto Contatos criado com sucesso!")

    def create_contacts_plans(self, product):
        """Criar planos específicos para o produto Contatos"""
        self.stdout.write("📋 Criando planos Contatos...")
        
        # Contatos Basic (Addon)
        contacts_basic, created = Plan.objects.get_or_create(
            slug='contacts-basic',
            defaults={
                'name': 'Contatos Basic',
                'description': 'Gestão básica de contatos - até 1.000 contatos e tags simples',
                'price': 19.90,
                'is_active': True,
                'color': '#3B82F6',
                'sort_order': 30
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {contacts_basic.name}")
        
        # Contatos Pro (Addon)
        contacts_pro, created = Plan.objects.get_or_create(
            slug='contacts-pro',
            defaults={
                'name': 'Contatos Pro',
                'description': 'Gestão avançada de contatos - até 10.000 contatos, segmentação e automação',
                'price': 59.90,
                'is_active': True,
                'color': '#2563EB',
                'sort_order': 31
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {contacts_pro.name}")
        
        # Contatos Unlimited (Addon)
        contacts_unlimited, created = Plan.objects.get_or_create(
            slug='contacts-unlimited',
            defaults={
                'name': 'Contatos Unlimited',
                'description': 'Gestão ilimitada de contatos - contatos ilimitados e todos os recursos avançados',
                'price': 149.90,
                'is_active': True,
                'color': '#1D4ED8',
                'sort_order': 32
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {contacts_unlimited.name}")



