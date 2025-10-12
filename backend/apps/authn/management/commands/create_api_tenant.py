from django.core.management.base import BaseCommand
from apps.tenancy.models import Tenant
from apps.billing.models import Plan
from apps.authn.models import User


class Command(BaseCommand):
    help = 'Cria um tenant API Only para desenvolvedores testarem'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando tenant API Only...")
        
        # Criar tenant para desenvolvedor
        api_tenant, created = Tenant.objects.get_or_create(
            name='Dev Company API',
            defaults={
                'status': 'active'
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Tenant criado: {api_tenant.name}")
        else:
            self.stdout.write(f"  ℹ️ Tenant já existe: {api_tenant.name}")
        
        # Associar plano API Pro
        try:
            api_pro_plan = Plan.objects.get(slug='api-pro')
            api_tenant.current_plan = api_pro_plan
            api_tenant.save()
            self.stdout.write(f"  ✅ Plano associado: {api_pro_plan.name}")
        except Plan.DoesNotExist:
            self.stdout.write("  ⚠️ Plano API Pro não encontrado")
        
        # Criar usuário desenvolvedor
        dev_user, created = User.objects.get_or_create(
            email='dev@api.com',
            defaults={
                'username': 'dev@api.com',
                'password': 'pbkdf2_sha256$600000$dev$dev',  # senha: dev123
                'first_name': 'Developer',
                'last_name': 'API',
                'tenant': api_tenant,
                'is_active': True
            }
        )
        
        if created:
            # Definir senha corretamente
            dev_user.set_password('dev123')
            dev_user.save()
            self.stdout.write(f"  ✅ Usuário criado: {dev_user.email} (senha: dev123)")
        else:
            self.stdout.write(f"  ℹ️ Usuário já existe: {dev_user.email}")
        
        self.stdout.write("\n🎯 Dados para teste API:")
        self.stdout.write(f"  • Tenant: {api_tenant.name}")
        self.stdout.write(f"  • Plano: {api_tenant.current_plan.name if api_tenant.current_plan else 'Nenhum'}")
        self.stdout.write(f"  • Email: dev@api.com")
        self.stdout.write(f"  • Senha: dev123")
        self.stdout.write(f"  • Acesso: Apenas API (sem UI)")
        self.stdout.write("\n✅ Tenant API Only criado com sucesso!")


