from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Corrige a estrutura de produtos e addons'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Corrigindo estrutura de produtos e addons...")
        
        # Buscar produtos
        flow_product = Product.objects.get(slug='flow')
        contacts_product = Product.objects.get(slug='contacts')
        sense_product = Product.objects.get(slug='sense')
        
        # Configurar Flow nos planos Flow (incluído por padrão)
        flow_plans = ['flow-starter', 'flow-pro', 'flow-enterprise']
        
        for plan_slug in flow_plans:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                
                # Flow incluído no plano
                flow_plan_product, created = PlanProduct.objects.get_or_create(
                    plan=plan,
                    product=flow_product,
                    defaults={
                        'is_included': True,  # Incluído no plano
                        'is_addon_available': False,  # Não é addon
                        'limit_value': self.get_flow_limit(plan_slug),
                        'limit_unit': 'instâncias'
                    }
                )
                
                if created:
                    self.stdout.write(f"  ✅ Flow configurado: {plan.name}")
                else:
                    flow_plan_product.is_included = True
                    flow_plan_product.is_addon_available = False
                    flow_plan_product.limit_value = self.get_flow_limit(plan_slug)
                    flow_plan_product.limit_unit = 'instâncias'
                    flow_plan_product.save()
                    self.stdout.write(f"  ✅ Flow atualizado: {plan.name}")
                    
            except Plan.DoesNotExist:
                self.stdout.write(f"  ⚠️ Plano {plan_slug} não encontrado")
        
        # Remover planos individuais de Sense e Contatos (são addons, não planos)
        individual_plans = [
            'sense-basic', 'sense-advanced', 'sense-unlimited',
            'contacts-basic', 'contacts-pro', 'contacts-unlimited'
        ]
        
        for plan_slug in individual_plans:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                plan.delete()
                self.stdout.write(f"  🗑️ Plano removido: {plan.name} (é addon, não plano)")
            except Plan.DoesNotExist:
                pass
        
        self.stdout.write("\n✅ Estrutura corrigida!")
        self.stdout.write("\n📋 Nova estrutura:")
        self.stdout.write("• Flow: Produto principal incluído nos planos Flow")
        self.stdout.write("• Sense: Addon disponível nos planos Flow")
        self.stdout.write("• Contatos: Addon disponível nos planos Flow")
        self.stdout.write("• API Only: Produto principal com planos próprios")

    def get_flow_limit(self, plan_slug):
        """Define limite de instâncias por plano Flow"""
        limits = {
            'flow-starter': 1,         # 1 instância
            'flow-pro': 3,             # 3 instâncias
            'flow-enterprise': None    # Ilimitado
        }
        return limits.get(plan_slug, 1)


