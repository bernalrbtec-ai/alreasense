"""
Management command para criar o produto Chat
"""
from django.core.management.base import BaseCommand
from apps.billing.models import Product


class Command(BaseCommand):
    help = 'Cria o produto Chat no sistema'

    def handle(self, *args, **options):
        # Verificar se já existe
        chat_product, created = Product.objects.get_or_create(
            slug='chat',
            defaults={
                'name': 'ALREA Chat',
                'description': 'Sistema de chat em tempo real integrado ao WhatsApp via Evolution API. Atendimento multi-agente, transferências entre departamentos, upload de arquivos e histórico completo.',
                'is_active': True,
                'requires_ui_access': True,
                'addon_price': 79.00,
                'icon': '💬',
                'color': '#10B981'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Produto Chat criado com sucesso! ID: {chat_product.id}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Produto Chat já existe! ID: {chat_product.id}')
            )
            
        # Mostrar info
        self.stdout.write(f"\n📦 Produto Chat:")
        self.stdout.write(f"   Nome: {chat_product.name}")
        self.stdout.write(f"   Slug: {chat_product.slug}")
        self.stdout.write(f"   Ativo: {chat_product.is_active}")
        self.stdout.write(f"   Descrição: {chat_product.description[:80]}...")

