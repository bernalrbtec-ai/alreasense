from django.core.management.base import BaseCommand
from apps.billing.models import Product, Plan, PlanProduct


class Command(BaseCommand):
    help = 'Mostra a estrutura de produtos e addons configurada'

    def handle(self, *args, **options):
        self.stdout.write("📦 ESTRUTURA DE PRODUTOS E ADDONS:")
        self.stdout.write("=" * 60)
        
        # Mostrar produtos principais
        self.stdout.write("\n🎯 PRODUTOS PRINCIPAIS:")
        main_products = Product.objects.filter(addon_price__isnull=True)
        for product in main_products:
            self.stdout.write(f"  • {product.icon} {product.name}")
            self.stdout.write(f"    Slug: {product.slug}")
            self.stdout.write(f"    UI Access: {'Sim' if product.requires_ui_access else 'Não'}")
            self.stdout.write()
        
        # Mostrar addons
        self.stdout.write("🔧 ADDONS DISPONÍVEIS:")
        addon_products = Product.objects.filter(addon_price__isnull=False)
        for product in addon_products:
            self.stdout.write(f"  • {product.icon} {product.name}")
            self.stdout.write(f"    Slug: {product.slug}")
            self.stdout.write(f"    Preço base: R$ {product.addon_price}")
            self.stdout.write()
        
        # Mostrar planos e seus produtos/addons
        self.stdout.write("💳 PLANOS E SUAS CONFIGURAÇÕES:")
        self.stdout.write("=" * 60)
        
        for plan in Plan.objects.all().order_by('sort_order'):
            self.stdout.write(f"\n📋 {plan.name} (R$ {plan.price})")
            self.stdout.write(f"   Descrição: {plan.description}")
            
            # Produtos associados ao plano
            plan_products = PlanProduct.objects.filter(plan=plan)
            if plan_products.exists():
                for plan_product in plan_products:
                    status = "✅ Incluído" if plan_product.is_included else "🔧 Addon disponível"
                    limit = f" (limite: {plan_product.limit_value} {plan_product.limit_unit})" if plan_product.limit_value else " (ilimitado)"
                    self.stdout.write(f"   • {plan_product.product.icon} {plan_product.product.name}: {status}{limit}")
            else:
                self.stdout.write("   • Nenhum produto associado")
        
        self.stdout.write("\n🎯 RESUMO DA ESTRATÉGIA:")
        self.stdout.write("=" * 60)
        self.stdout.write("• Flow: Produto principal (automação de conversas)")
        self.stdout.write("• API Only: Produto principal (apenas para desenvolvedores)")
        self.stdout.write("• Sense: Addon (análise de IA)")
        self.stdout.write("• Contatos: Addon (gestão de leads)")
        self.stdout.write()
        self.stdout.write("✅ Clientes contratam Flow + addons conforme necessidade")
        self.stdout.write("✅ Desenvolvedores contratam API Only")
        self.stdout.write("✅ Sistema de limites por plano funcionando")


