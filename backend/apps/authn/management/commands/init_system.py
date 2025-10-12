from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.billing.models import Product, Plan
from apps.tenancy.models import Tenant
from apps.authn.models import User


class Command(BaseCommand):
    help = 'Inicializa o sistema com dados básicos'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Inicializando sistema...")
        
        # Criar produtos e planos
        self.create_billing_data()
        
        # Criar superusuário
        self.create_superuser()
        
        self.stdout.write("✅ Sistema inicializado com sucesso!")

    def create_billing_data(self):
        """Criar produtos e planos básicos"""
        self.stdout.write("📦 Criando produtos e planos...")
        
        # Produto WhatsApp
        product, created = Product.objects.get_or_create(
            name='WhatsApp Business',
            defaults={
                'description': 'Plataforma de automação WhatsApp',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Produto criado: {product.name}")
        
        # Plano Free
        free_plan, created = Plan.objects.get_or_create(
            slug='free',
            defaults={
                'name': 'Free',
                'description': 'Plano gratuito com funcionalidades básicas',
                'price': 0.00,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {free_plan.name}")
        
        # Plano Pro
        pro_plan, created = Plan.objects.get_or_create(
            slug='pro',
            defaults={
                'name': 'Pro',
                'description': 'Plano profissional com recursos avançados',
                'price': 49.90,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {pro_plan.name}")
        
        # Plano Enterprise
        enterprise_plan, created = Plan.objects.get_or_create(
            slug='enterprise',
            defaults={
                'name': 'Enterprise',
                'description': 'Plano empresarial com recursos ilimitados',
                'price': 199.90,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Plano criado: {enterprise_plan.name}")

    def create_superuser(self):
        """Criar superusuário padrão"""
        self.stdout.write("👤 Criando superusuário...")
        
        # Criar tenant para o admin
        from apps.tenancy.models import Tenant
        admin_tenant, created = Tenant.objects.get_or_create(
            name='Admin System'
        )
        
        if created:
            self.stdout.write(f"  ✅ Tenant criado: {admin_tenant.name}")
        
        if not User.objects.filter(email='admin@sense.com').exists():
            user = User.objects.create_superuser(
                username='admin@sense.com',
                email='admin@sense.com',
                password='admin123',
                first_name='Admin',
                last_name='Sense',
                tenant=admin_tenant
            )
            self.stdout.write(f"  ✅ Superusuário criado: {user.email}")
        else:
            self.stdout.write("  ℹ️ Superusuário já existe")
