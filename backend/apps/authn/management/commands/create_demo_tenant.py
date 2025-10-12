from django.core.management.base import BaseCommand
from apps.tenancy.models import Tenant
from apps.billing.models import Plan
from apps.authn.models import User


class Command(BaseCommand):
    help = 'Cria um tenant de demonstração com produtos Flow e Sense'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando tenant de demonstração...")
        
        # Criar tenant de demo
        demo_tenant, created = Tenant.objects.get_or_create(
            name='Empresa Demo',
            defaults={
                'status': 'active'
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Tenant criado: {demo_tenant.name}")
        else:
            self.stdout.write(f"  ℹ️ Tenant já existe: {demo_tenant.name}")
        
        # Associar plano Flow Pro
        try:
            flow_pro_plan = Plan.objects.get(slug='flow-pro')
            demo_tenant.current_plan = flow_pro_plan
            demo_tenant.save()
            self.stdout.write(f"  ✅ Plano associado: {flow_pro_plan.name}")
        except Plan.DoesNotExist:
            self.stdout.write("  ⚠️ Plano Flow Pro não encontrado")
        
        # Criar usuário demo
        demo_user, created = User.objects.get_or_create(
            email='demo@empresa.com',
            defaults={
                'username': 'demo@empresa.com',
                'password': 'pbkdf2_sha256$600000$demo$demo',  # senha: demo123
                'first_name': 'Usuário',
                'last_name': 'Demo',
                'tenant': demo_tenant,
                'is_active': True
            }
        )
        
        if created:
            # Definir senha corretamente
            demo_user.set_password('demo123')
            demo_user.save()
            self.stdout.write(f"  ✅ Usuário criado: {demo_user.email} (senha: demo123)")
        else:
            self.stdout.write(f"  ℹ️ Usuário já existe: {demo_user.email}")
        
        self.stdout.write("\n🎯 Dados para teste:")
        self.stdout.write(f"  • Tenant: {demo_tenant.name}")
        self.stdout.write(f"  • Plano: {demo_tenant.current_plan.name if demo_tenant.current_plan else 'Nenhum'}")
        self.stdout.write(f"  • Email: demo@empresa.com")
        self.stdout.write(f"  • Senha: demo123")
        self.stdout.write("\n✅ Tenant de demonstração criado com sucesso!")



