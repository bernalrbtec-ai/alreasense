"""
Comando para criar o produto Workflow (Chat + Agenda/Tarefas)
"""
from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct
from decimal import Decimal


class Command(BaseCommand):
    help = 'Cria o produto Workflow (Chat + Agenda/Tarefas) e adiciona aos planos existentes'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando produto Workflow...")
        
        # Criar produto Workflow
        workflow_product, created = Product.objects.get_or_create(
            slug='workflow',
            defaults={
                'name': 'ALREA Workflow',
                'description': 'Chat e Agenda/Tarefas integrados para gestão de atendimento e organização',
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': Decimal('29.90'),  # Pode ser add-on
                'icon': '💬',
                'color': '#10B981'  # Verde (mesma cor do Flow)
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto Workflow criado: {workflow_product.name}")
        else:
            self.stdout.write(f"  ℹ️ Produto Workflow já existe: {workflow_product.name}")
            # Atualizar se necessário
            workflow_product.name = 'ALREA Workflow'
            workflow_product.description = 'Chat e Agenda/Tarefas integrados para gestão de atendimento e organização'
            workflow_product.is_active = True
            workflow_product.requires_ui_access = True
            workflow_product.addon_price = Decimal('29.90')
            workflow_product.icon = '💬'
            workflow_product.color = '#10B981'
            workflow_product.save()
            self.stdout.write(f"  🔄 Produto Workflow atualizado")
        
        # Adicionar workflow a todos os planos ativos
        self.stdout.write("📋 Adicionando Workflow aos planos existentes...")
        
        active_plans = Plan.objects.filter(is_active=True)
        added_count = 0
        updated_count = 0
        
        for plan in active_plans:
            plan_product, created = PlanProduct.objects.get_or_create(
                plan=plan,
                product=workflow_product,
                defaults={
                    'is_included': True,
                    'is_addon_available': True,
                    'limit_value': None,  # Ilimitado por padrão
                    'limit_unit': None
                }
            )
            
            if created:
                added_count += 1
                self.stdout.write(f"  ✅ Adicionado ao plano: {plan.name}")
            else:
                # Atualizar se já existe mas não está incluído
                if not plan_product.is_included:
                    plan_product.is_included = True
                    plan_product.save()
                    updated_count += 1
                    self.stdout.write(f"  🔄 Atualizado no plano: {plan.name}")
                else:
                    self.stdout.write(f"  ℹ️ Já existe no plano: {plan.name}")
        
        self.stdout.write(f"\n✅ Produto Workflow configurado!")
        self.stdout.write(f"   - Produto criado/atualizado: {workflow_product.name}")
        self.stdout.write(f"   - Adicionado a {added_count} plano(s)")
        self.stdout.write(f"   - Atualizado em {updated_count} plano(s)")
        self.stdout.write(f"   - Total de planos processados: {active_plans.count()}")

