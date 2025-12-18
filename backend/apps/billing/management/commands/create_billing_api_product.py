"""
Management command para criar produto Integração
"""
from django.core.management.base import BaseCommand
from apps.billing.models import Product


class Command(BaseCommand):
    help = 'Cria o produto Integração no sistema de produtos'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando produto Integração...")
        
        # Produto Integração (API de Billing)
        integracao_product, created = Product.objects.get_or_create(
            slug='integracao',
            defaults={
                'name': 'Integração',
                'description': 'API para envio de cobranças e notificações via WhatsApp. Permite integração externa para sistemas ERP/CRM enviarem cobranças automaticamente. Documentação completa com exemplos e configurações disponível.',
                'is_active': True,
                'requires_ui_access': True,  # Tem UI com documentação
                'addon_price': 99.00,  # Pode ser add-on (R$ 99/mês)
                'icon': '🔌',
                'color': '#10B981'  # Verde (integração)
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✅ Produto Integração criado: {integracao_product.name} "
                    f"(slug: {integracao_product.slug})"
                )
            )
            self.stdout.write(
                f"  💰 Preço como add-on: R$ {integracao_product.addon_price}/mês"
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  ℹ️ Produto Integração já existe: {integracao_product.name}"
                )
            )
        
        self.stdout.write("\n✅ Comando executado com sucesso!")

