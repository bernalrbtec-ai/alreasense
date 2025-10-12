from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan
from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = 'Lista todos os produtos, planos e tenants criados'

    def handle(self, *args, **options):
        self.stdout.write("📦 PRODUTOS DISPONÍVEIS:")
        self.stdout.write("=" * 50)
        
        for product in Product.objects.all():
            self.stdout.write(f"• {product.icon} {product.name} ({product.slug})")
            self.stdout.write(f"  Descrição: {product.description}")
            self.stdout.write(f"  UI Access: {'Sim' if product.requires_ui_access else 'Não'}")
            self.stdout.write(f"  Addon Price: R$ {product.addon_price if product.addon_price else 'N/A'}")
            self.stdout.write()

        self.stdout.write("💳 PLANOS DISPONÍVEIS:")
        self.stdout.write("=" * 50)
        
        for plan in Plan.objects.all().order_by('sort_order'):
            self.stdout.write(f"• {plan.name} ({plan.slug})")
            self.stdout.write(f"  Preço: R$ {plan.price}")
            self.stdout.write(f"  Descrição: {plan.description}")
            self.stdout.write()

        self.stdout.write("🏢 TENANTS CRIADOS:")
        self.stdout.write("=" * 50)
        
        for tenant in Tenant.objects.all():
            plan_name = tenant.current_plan.name if tenant.current_plan else 'Nenhum'
            self.stdout.write(f"• {tenant.name} - Plano: {plan_name}")
        
        self.stdout.write("\n✅ Listagem completa!")



