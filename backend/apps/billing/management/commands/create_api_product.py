from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan


class Command(BaseCommand):
    help = 'Cria o produto API Only para desenvolvedores'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando produto API Only...")
        
        # Produto API Only
        api_product, created = Product.objects.get_or_create(
            slug='api_public',
            defaults={
                'name': 'API Only',
                'description': 'Acesso apenas à API pública e instâncias WhatsApp - ideal para desenvolvedores e integrações',
                'is_active': True,
                'requires_ui_access': False,  # Não precisa de acesso à UI
                'addon_price': None,  # Produto principal
                'icon': '🔌',
                'color': '#F59E0B'  # Laranja
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto API Only criado: {api_product.name}")
        else:
            self.stdout.write(f"  ℹ️ Produto API Only já existe: {api_product.name}")
        
        # Criar planos específicos para API Only
        self.create_api_plans(api_product)
        
        self.stdout.write("✅ Produto API Only criado com sucesso!")

    def create_api_plans(self, product):
        """Criar planos específicos para o produto API Only"""
        self.stdout.write("📋 Criando planos API Only...")
        
        # API Starter
        api_starter, created = Plan.objects.get_or_create(
            slug='api-starter',
            defaults={
                'name': 'API Starter',
                'description': 'API básica para desenvolvedores - até 1 instância WhatsApp e 1.000 requests/dia',
                'price': 29.90,
                'is_active': True,
                'color': '#F59E0B',
                'sort_order': 20
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {api_starter.name}")
        
        # API Pro
        api_pro, created = Plan.objects.get_or_create(
            slug='api-pro',
            defaults={
                'name': 'API Pro',
                'description': 'API avançada para empresas - até 3 instâncias WhatsApp e 10.000 requests/dia',
                'price': 99.90,
                'is_active': True,
                'color': '#D97706',
                'sort_order': 21
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {api_pro.name}")
        
        # API Scale
        api_scale, created = Plan.objects.get_or_create(
            slug='api-scale',
            defaults={
                'name': 'API Scale',
                'description': 'API para alta escala - até 10 instâncias WhatsApp e 100.000 requests/dia',
                'price': 299.90,
                'is_active': True,
                'color': '#B45309',
                'sort_order': 22
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {api_scale.name}")
        
        # API Enterprise
        api_enterprise, created = Plan.objects.get_or_create(
            slug='api-enterprise',
            defaults={
                'name': 'API Enterprise',
                'description': 'API empresarial - instâncias ilimitadas, requests ilimitados e suporte premium',
                'price': 999.90,
                'is_active': True,
                'color': '#92400E',
                'sort_order': 23
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {api_enterprise.name}")


