from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Configura Contatos como incluído por padrão nos planos Flow'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Configurando Contatos como padrão nos planos Flow...")
        
        # Buscar o produto Contatos
        try:
            contacts_product = Product.objects.get(slug='contacts')
            self.stdout.write(f"  ✅ Produto encontrado: {contacts_product.name}")
        except Product.DoesNotExist:
            self.stdout.write("  ❌ Produto Contatos não encontrado")
            return
        
        # Configurar Contatos como incluído nos planos Flow
        flow_plans = ['flow-starter', 'flow-pro', 'flow-enterprise']
        
        for plan_slug in flow_plans:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                
                # Criar ou atualizar associação
                plan_product, created = PlanProduct.objects.get_or_create(
                    plan=plan,
                    product=contacts_product,
                    defaults={
                        'is_included': True,  # INCLUÍDO por padrão
                        'is_addon_available': False,  # Não é addon
                        'limit_value': self.get_contacts_limit(plan_slug),
                        'limit_unit': 'contatos'
                    }
                )
                
                if created:
                    self.stdout.write(f"  ✅ Contatos incluído: {plan.name} → {contacts_product.name}")
                else:
                    # Atualizar para incluído
                    plan_product.is_included = True
                    plan_product.is_addon_available = False
                    plan_product.limit_value = self.get_contacts_limit(plan_slug)
                    plan_product.limit_unit = 'contatos'
                    plan_product.save()
                    self.stdout.write(f"  ✅ Contatos atualizado: {plan.name} → {contacts_product.name}")
                    
            except Plan.DoesNotExist:
                self.stdout.write(f"  ⚠️ Plano {plan_slug} não encontrado")
        
        self.stdout.write("\n✅ Configuração de Contatos concluída!")
        self.stdout.write("\n📋 Como funciona agora:")
        self.stdout.write("• Contatos está INCLUÍDO em todos os planos Flow")
        self.stdout.write("• Clientes que assinam Flow já têm gestão de contatos")
        self.stdout.write("• Limites são definidos por plano (Starter: 1K, Pro: 10K, Enterprise: ilimitado)")
        self.stdout.write("• Funcionalidades de gestão de contatos ficam habilitadas automaticamente")

    def get_contacts_limit(self, plan_slug):
        """Define limite de contatos por plano"""
        limits = {
            'flow-starter': 1000,      # 1K contatos
            'flow-pro': 10000,         # 10K contatos
            'flow-enterprise': None    # Ilimitado
        }
        return limits.get(plan_slug, 1000)


