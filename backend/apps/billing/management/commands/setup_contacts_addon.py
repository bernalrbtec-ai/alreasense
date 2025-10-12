from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Configura o produto Contatos como addon nos planos Flow'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Configurando Contatos como addon...")
        
        # Buscar o produto Contatos
        try:
            contacts_product = Product.objects.get(slug='contacts')
            self.stdout.write(f"  ✅ Produto encontrado: {contacts_product.name}")
        except Product.DoesNotExist:
            self.stdout.write("  ❌ Produto Contatos não encontrado")
            return
        
        # Configurar nos planos Flow
        flow_plans = ['flow-starter', 'flow-pro', 'flow-enterprise']
        
        for plan_slug in flow_plans:
            try:
                plan = Plan.objects.get(slug=plan_slug)
                
                # Criar ou atualizar associação
                plan_product, created = PlanProduct.objects.get_or_create(
                    plan=plan,
                    product=contacts_product,
                    defaults={
                        'is_included': False,  # Não incluído por padrão
                        'is_addon_available': True,  # Disponível como addon
                        'limit_value': self.get_contacts_limit(plan_slug),
                        'limit_unit': 'contatos'
                    }
                )
                
                if created:
                    self.stdout.write(f"  ✅ Addon configurado: {plan.name} → {contacts_product.name}")
                else:
                    # Atualizar se já existir
                    plan_product.is_addon_available = True
                    plan_product.limit_value = self.get_contacts_limit(plan_slug)
                    plan_product.limit_unit = 'contatos'
                    plan_product.save()
                    self.stdout.write(f"  ✅ Addon atualizado: {plan.name} → {contacts_product.name}")
                    
            except Plan.DoesNotExist:
                self.stdout.write(f"  ⚠️ Plano {plan_slug} não encontrado")
        
        self.stdout.write("\n✅ Configuração de addon Contatos concluída!")
        self.stdout.write("\n📋 Como funciona:")
        self.stdout.write("• Contatos NÃO está incluído nos planos Flow por padrão")
        self.stdout.write("• Clientes podem contratar Contatos como addon")
        self.stdout.write("• Limites são definidos por plano (Starter: 1K, Pro: 10K, Enterprise: ilimitado)")
        self.stdout.write("• Funcionalidades de gestão de contatos ficam habilitadas quando contratado")

    def get_contacts_limit(self, plan_slug):
        """Define limite de contatos por plano"""
        limits = {
            'flow-starter': 1000,      # 1K contatos
            'flow-pro': 10000,         # 10K contatos
            'flow-enterprise': None    # Ilimitado
        }
        return limits.get(plan_slug, 1000)


