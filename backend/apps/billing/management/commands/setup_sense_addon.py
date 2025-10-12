from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Configura o produto Sense como addon nos planos Flow'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Configurando Sense como addon...")
        
        # Buscar o produto Sense
        try:
            sense_product = Product.objects.get(slug='sense')
            self.stdout.write(f"  ✅ Produto encontrado: {sense_product.name}")
        except Product.DoesNotExist:
            self.stdout.write("  ❌ Produto Sense não encontrado")
            return
        
        # Configurar nos planos Flow
        flow_plans = ['flow-starter', 'flow-pro', 'flow-enterprise']
        
        for plan_slug in flow_plans:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                
                # Criar ou atualizar associação
                plan_product, created = PlanProduct.objects.get_or_create(
                    plan=plan,
                    product=sense_product,
                    defaults={
                        'is_included': False,  # Não incluído por padrão
                        'is_addon_available': True,  # Disponível como addon
                        'limit_value': self.get_sense_limit(plan_slug),
                        'limit_unit': 'análises/mês'
                    }
                )
                
                if created:
                    self.stdout.write(f"  ✅ Addon configurado: {plan.name} → {sense_product.name}")
                else:
                    # Atualizar se já existir
                    plan_product.is_addon_available = True
                    plan_product.limit_value = self.get_sense_limit(plan_slug)
                    plan_product.limit_unit = 'análises/mês'
                    plan_product.save()
                    self.stdout.write(f"  ✅ Addon atualizado: {plan.name} → {sense_product.name}")
                    
            except Plan.DoesNotExist:
                self.stdout.write(f"  ⚠️ Plano {plan_slug} não encontrado")
        
        self.stdout.write("\n✅ Configuração de addon Sense concluída!")
        self.stdout.write("\n📋 Como funciona:")
        self.stdout.write("• Sense NÃO está incluído nos planos Flow por padrão")
        self.stdout.write("• Clientes podem contratar Sense como addon")
        self.stdout.write("• Limites são definidos por plano (Starter: 1K, Pro: 10K, Enterprise: ilimitado)")
        self.stdout.write("• Funcionalidades de IA ficam habilitadas quando contratado")

    def get_sense_limit(self, plan_slug):
        """Define limite de análises por plano"""
        limits = {
            'flow-starter': 1000,      # 1K análises/mês
            'flow-pro': 10000,         # 10K análises/mês
            'flow-enterprise': None    # Ilimitado
        }
        return limits.get(plan_slug, 1000)



