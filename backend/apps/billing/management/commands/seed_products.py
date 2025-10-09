"""
Comando para popular produtos e planos iniciais
Baseado na estratégia definida em ALREA_PRODUCTS_STRATEGY.md
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Popula produtos e planos iniciais da plataforma ALREA'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Iniciando seed de produtos e planos...')
        
        # Verificar se as tabelas existem
        try:
            Product.objects.count()
            tables_exist = True
        except Exception:
            tables_exist = False
        
        if tables_exist:
            with transaction.atomic():
                # Limpar dados existentes
                self.stdout.write('🧹 Limpando dados existentes...')
                PlanProduct.objects.all().delete()
                Plan.objects.all().delete()
                Product.objects.all().delete()
                
                # Criar produtos
                self.stdout.write('📦 Criando produtos...')
                products = self.create_products()
                
                # Criar planos
                self.stdout.write('💳 Criando planos...')
                plans = self.create_plans()
                
                # Criar relacionamentos plano-produto
                self.stdout.write('🔗 Criando relacionamentos plano-produto...')
                self.create_plan_products(products, plans)
        else:
            # Criar produtos sem transação
            self.stdout.write('📦 Criando produtos...')
            products = self.create_products()
            
            # Criar planos
            self.stdout.write('💳 Criando planos...')
            plans = self.create_plans()
            
            # Criar relacionamentos plano-produto
            self.stdout.write('🔗 Criando relacionamentos plano-produto...')
            self.create_plan_products(products, plans)
            
        self.stdout.write(
            self.style.SUCCESS('✅ Seed concluído com sucesso!')
        )
        
        # Mostrar resumo
        self.show_summary()

    def create_products(self):
        """Cria os produtos da plataforma"""
        products_data = [
            {
                'slug': 'flow',
                'name': 'ALREA Flow',
                'description': 'Sistema completo de campanhas de disparo em massa via WhatsApp',
                'icon': '📤',
                'color': '#10B981',
                'requires_ui_access': True,
                'addon_price': None,  # Não é add-on, está incluído nos planos
            },
            {
                'slug': 'sense',
                'name': 'ALREA Sense',
                'description': 'Monitoramento e análise de conversas WhatsApp com IA',
                'icon': '🧠',
                'color': '#8B5CF6',
                'requires_ui_access': True,
                'addon_price': None,  # Não é add-on, está incluído nos planos
            },
            {
                'slug': 'api_public',
                'name': 'ALREA API Pública',
                'description': 'Endpoints REST documentados para integração com sistemas externos',
                'icon': '🔌',
                'color': '#F59E0B',
                'requires_ui_access': False,  # API Only não precisa de UI
                'addon_price': 79.00,  # Pode ser add-on
            },
        ]
        
        products = {}
        for data in products_data:
            product, created = Product.objects.get_or_create(
                slug=data['slug'],
                defaults=data
            )
            products[data['slug']] = product
            status = 'criado' if created else 'atualizado'
            self.stdout.write(f'  {product.icon} {product.name} - {status}')
        
        return products

    def create_plans(self):
        """Cria os planos de assinatura"""
        plans_data = [
            {
                'slug': 'starter',
                'name': 'Starter',
                'description': 'Ideal para pequenas empresas e autônomos',
                'price': 49.00,
                'color': '#3B82F6',
                'sort_order': 1,
            },
            {
                'slug': 'pro',
                'name': 'Pro',
                'description': 'Solução completa para empresas em crescimento',
                'price': 149.00,
                'color': '#8B5CF6',
                'sort_order': 2,
            },
            {
                'slug': 'api_only',
                'name': 'API Only',
                'description': 'Apenas API para desenvolvedores e integradores',
                'price': 99.00,
                'color': '#F59E0B',
                'sort_order': 3,
            },
            {
                'slug': 'enterprise',
                'name': 'Enterprise',
                'description': 'Tudo ilimitado para grandes empresas',
                'price': 499.00,
                'color': '#EF4444',
                'sort_order': 4,
            },
        ]
        
        plans = {}
        for data in plans_data:
            plan, created = Plan.objects.get_or_create(
                slug=data['slug'],
                defaults=data
            )
            plans[data['slug']] = plan
            status = 'criado' if created else 'atualizado'
            self.stdout.write(f'  💳 {plan.name} (R$ {plan.price}) - {status}')
        
        return plans

    def create_plan_products(self, products, plans):
        """Cria os relacionamentos entre planos e produtos"""
        plan_products_config = {
            'starter': {
                'flow': {'is_included': True, 'limit_value': 5, 'limit_unit': 'campanhas/mês'},
                'sense': {'is_included': False},
                'api_public': {'is_included': False, 'is_addon_available': True},
            },
            'pro': {
                'flow': {'is_included': True, 'limit_value': 20, 'limit_unit': 'campanhas/mês'},
                'sense': {'is_included': True, 'limit_value': 5000, 'limit_unit': 'análises/mês'},
                'api_public': {'is_included': False, 'is_addon_available': True},
            },
            'api_only': {
                'flow': {'is_included': False},
                'sense': {'is_included': False},
                'api_public': {'is_included': True, 'limit_value': 50000, 'limit_unit': 'requests/dia'},
            },
            'enterprise': {
                'flow': {'is_included': True},  # Ilimitado
                'sense': {'is_included': True},  # Ilimitado
                'api_public': {'is_included': True},  # Ilimitado
            },
        }
        
        for plan_slug, products_config in plan_products_config.items():
            plan = plans[plan_slug]
            self.stdout.write(f'  🔗 Configurando produtos para {plan.name}...')
            
            for product_slug, config in products_config.items():
                product = products[product_slug]
                
                plan_product, created = PlanProduct.objects.get_or_create(
                    plan=plan,
                    product=product,
                    defaults=config
                )
                
                status = 'criado' if created else 'atualizado'
                included = '✅' if config['is_included'] else '❌'
                limit = f" (limite: {config.get('limit_value', '∞')} {config.get('limit_unit', '')})" if config.get('limit_value') else ''
                self.stdout.write(f'    {included} {product.name}{limit} - {status}')

    def show_summary(self):
        """Mostra resumo dos dados criados"""
        self.stdout.write('\n📊 RESUMO:')
        self.stdout.write(f'  📦 Produtos: {Product.objects.count()}')
        self.stdout.write(f'  💳 Planos: {Plan.objects.count()}')
        self.stdout.write(f'  🔗 Relacionamentos: {PlanProduct.objects.count()}')
        
        self.stdout.write('\n💳 PLANOS DISPONÍVEIS:')
        for plan in Plan.objects.all().order_by('sort_order'):
            total = plan.plan_products.filter(is_included=True).count()
            self.stdout.write(f'  {plan.name}: R$ {plan.price}/mês ({total} produtos incluídos)')
        
        self.stdout.write('\n📦 PRODUTOS DISPONÍVEIS:')
        for product in Product.objects.all():
            addon_info = f" (add-on: R$ {product.addon_price}/mês)" if product.addon_price else ""
            self.stdout.write(f'  {product.icon} {product.name}{addon_info}')
