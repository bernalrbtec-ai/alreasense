from django.core.management.base import BaseCommand
from apps.tenancy.models import Tenant
from apps.billing.models import Plan
from apps.authn.models import User


class Command(BaseCommand):
    help = 'Cria um tenant completo com Flow + Sense + Contatos'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Criando tenant completo (Flow + Sense + Contatos)...")
        
        # Criar tenant completo
        full_tenant, created = Tenant.objects.get_or_create(
            name='Empresa Completa',
            defaults={
                'status': 'active'
            }
        )
        
        if created:
            self.stdout.write(f"  ✅ Tenant criado: {full_tenant.name}")
        else:
            self.stdout.write(f"  ℹ️ Tenant já existe: {full_tenant.name}")
        
        # Associar plano Flow Enterprise (mais completo)
        try:
            flow_enterprise_plan = Plan.objects.get(slug='flow-enterprise')
            full_tenant.current_plan = flow_enterprise_plan
            full_tenant.save()
            self.stdout.write(f"  ✅ Plano principal associado: {flow_enterprise_plan.name}")
        except Plan.DoesNotExist:
            self.stdout.write("  ⚠️ Plano Flow Enterprise não encontrado")
        
        # Criar usuário completo
        full_user, created = User.objects.get_or_create(
            email='completo@empresa.com',
            defaults={
                'username': 'completo@empresa.com',
                'password': 'pbkdf2_sha256$600000$completo$completo',  # senha: completo123
                'first_name': 'Empresa',
                'last_name': 'Completa',
                'tenant': full_tenant,
                'is_active': True
            }
        )
        
        if created:
            # Definir senha corretamente
            full_user.set_password('completo123')
            full_user.save()
            self.stdout.write(f"  ✅ Usuário criado: {full_user.email} (senha: completo123)")
        else:
            self.stdout.write(f"  ℹ️ Usuário já existe: {full_user.email}")
        
        self.stdout.write("\n🎯 Dados para teste completo:")
        self.stdout.write(f"  • Tenant: {full_tenant.name}")
        self.stdout.write(f"  • Plano Principal: {full_tenant.current_plan.name if full_tenant.current_plan else 'Nenhum'}")
        self.stdout.write(f"  • Email: completo@empresa.com")
        self.stdout.write(f"  • Senha: completo123")
        self.stdout.write(f"  • Produtos disponíveis: Flow, Sense, Contatos")
        self.stdout.write("\n✅ Tenant completo criado com sucesso!")



