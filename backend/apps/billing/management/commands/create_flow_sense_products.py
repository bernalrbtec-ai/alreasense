from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan


class Command(BaseCommand):
    help = 'Cria os produtos Flow e Sense para liberar para clientes'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando produtos Flow e Sense...")
        
        # Produto Flow (Automação de Conversas)
        flow_product, created = Product.objects.get_or_create(
            slug='flow',
            defaults={
                'name': 'Flow',
                'description': 'Automação inteligente de conversas WhatsApp com fluxos conversacionais e respostas automáticas',
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': None,  # Produto principal, não addon
                'icon': '💬',
                'color': '#10B981'  # Verde
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto Flow criado: {flow_product.name}")
        else:
            self.stdout.write(f"  ℹ️ Produto Flow já existe: {flow_product.name}")
        
        # Produto Sense (Análise de IA)
        sense_product, created = Product.objects.get_or_create(
            slug='sense',
            defaults={
                'name': 'Sense',
                'description': 'Análise de sentimento e satisfação com IA para insights em conversas WhatsApp',
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': 29.90,  # Pode ser addon
                'icon': '🧠',
                'color': '#8B5CF6'  # Roxo
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto Sense criado: {sense_product.name}")
        else:
            self.stdout.write(f"  ℹ️ Produto Sense já existe: {sense_product.name}")
        
        # Criar planos específicos para Flow
        self.create_flow_plans(flow_product)
        
        # Criar planos específicos para Sense (como addon)
        self.create_sense_plans(sense_product)
        
        self.stdout.write("✅ Produtos Flow e Sense criados com sucesso!")

    def create_flow_plans(self, product):
        """Criar planos específicos para o produto Flow"""
        self.stdout.write("📋 Criando planos Flow...")
        
        # Flow Starter
        flow_starter, created = Plan.objects.get_or_create(
            slug='flow-starter',
            defaults={
                'name': 'Flow Starter',
                'description': 'Automação básica para pequenos negócios - até 1 número WhatsApp',
                'price': 49.90,
                'is_active': True,
                'color': '#10B981',
                'sort_order': 1
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {flow_starter.name}")
        
        # Flow Pro
        flow_pro, created = Plan.objects.get_or_create(
            slug='flow-pro',
            defaults={
                'name': 'Flow Pro',
                'description': 'Automação avançada para empresas - até 3 números WhatsApp',
                'price': 149.90,
                'is_active': True,
                'color': '#059669',
                'sort_order': 2
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {flow_pro.name}")
        
        # Flow Enterprise
        flow_enterprise, created = Plan.objects.get_or_create(
            slug='flow-enterprise',
            defaults={
                'name': 'Flow Enterprise',
                'description': 'Automação empresarial - números ilimitados e recursos premium',
                'price': 499.90,
                'is_active': True,
                'color': '#047857',
                'sort_order': 3
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {flow_enterprise.name}")

    def create_sense_plans(self, product):
        """Criar planos específicos para o produto Sense"""
        self.stdout.write("📊 Criando planos Sense...")
        
        # Sense Basic (Addon)
        sense_basic, created = Plan.objects.get_or_create(
            slug='sense-basic',
            defaults={
                'name': 'Sense Basic',
                'description': 'Análise básica de sentimento - até 1.000 mensagens/mês',
                'price': 29.90,
                'is_active': True,
                'color': '#8B5CF6',
                'sort_order': 10
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {sense_basic.name}")
        
        # Sense Advanced (Addon)
        sense_advanced, created = Plan.objects.get_or_create(
            slug='sense-advanced',
            defaults={
                'name': 'Sense Advanced',
                'description': 'Análise avançada com insights detalhados - até 10.000 mensagens/mês',
                'price': 99.90,
                'is_active': True,
                'color': '#7C3AED',
                'sort_order': 11
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {sense_advanced.name}")
        
        # Sense Unlimited (Addon)
        sense_unlimited, created = Plan.objects.get_or_create(
            slug='sense-unlimited',
            defaults={
                'name': 'Sense Unlimited',
                'description': 'Análise ilimitada com todos os recursos de IA',
                'price': 199.90,
                'is_active': True,
                'color': '#6D28D9',
                'sort_order': 12
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {sense_unlimited.name}")


