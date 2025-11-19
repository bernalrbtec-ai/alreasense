"""
Comando Django para corrigir o admin do sistema
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()


class Command(BaseCommand):
    help = 'Corrige o admin do sistema: promove paulo.bernal@alrea.ai e desativa admin@alreasense.com'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('🔧 CORRIGINDO ADMIN DO SISTEMA'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        # Email correto do admin
        CORRECT_ADMIN_EMAIL = 'paulo.bernal@alrea.ai'
        OLD_ADMIN_EMAIL = 'admin@alreasense.com'
        
        # 1. Verificar se paulo.bernal@alrea.ai existe
        self.stdout.write(f"1️⃣ Verificando usuário {CORRECT_ADMIN_EMAIL}...")
        correct_admin = User.objects.filter(email=CORRECT_ADMIN_EMAIL).first()
        
        if not correct_admin:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Usuário {CORRECT_ADMIN_EMAIL} não encontrado!"))
            self.stdout.write(f"   📝 Criando novo usuário...")
            
            # Buscar tenant padrão
            tenant = Tenant.objects.filter(name='Default Tenant').first()
            if not tenant:
                tenant = Tenant.objects.first()
                if not tenant:
                    self.stdout.write(self.style.ERROR(f"   ❌ Nenhum tenant encontrado! Criando tenant padrão..."))
                    from apps.billing.models import Plan
                    starter_plan = Plan.objects.filter(slug='starter').first()
                    tenant = Tenant.objects.create(
                        name='Default Tenant',
                        current_plan=starter_plan,
                        ui_access=True
                    )
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Tenant criado: {tenant.name}"))
            
            # Criar usuário
            correct_admin = User.objects.create_user(
                username=CORRECT_ADMIN_EMAIL,
                email=CORRECT_ADMIN_EMAIL,
                password='admin123',  # Senha padrão (usuário pode alterar depois)
                first_name='Paulo',
                last_name='Bernal',
                tenant=tenant,
                is_superuser=True,
                is_staff=True,
                is_active=True,
                role='admin'
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Usuário criado: {correct_admin.email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"   ✅ Usuário encontrado: {correct_admin.email}"))
        
        # 2. Promover paulo.bernal@alrea.ai a superuser
        self.stdout.write(f"\n2️⃣ Promovendo {CORRECT_ADMIN_EMAIL} a superuser...")
        correct_admin.is_superuser = True
        correct_admin.is_staff = True
        correct_admin.is_active = True
        correct_admin.role = 'admin'
        correct_admin.save()
        self.stdout.write(self.style.SUCCESS(f"   ✅ Permissões atualizadas:"))
        self.stdout.write(f"      - is_superuser: {correct_admin.is_superuser}")
        self.stdout.write(f"      - is_staff: {correct_admin.is_staff}")
        self.stdout.write(f"      - role: {correct_admin.role}")
        
        # 3. Remover ou desativar admin@alreasense.com
        self.stdout.write(f"\n3️⃣ Verificando usuário {OLD_ADMIN_EMAIL}...")
        old_admin = User.objects.filter(email=OLD_ADMIN_EMAIL).first()
        
        if old_admin:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Usuário {OLD_ADMIN_EMAIL} encontrado!"))
            
            # Se for o mesmo usuário (caso email foi alterado), não fazer nada
            if old_admin.id == correct_admin.id:
                self.stdout.write(self.style.SUCCESS(f"   ℹ️  É o mesmo usuário (email foi alterado), mantendo..."))
            else:
                # Remover permissões de superuser
                self.stdout.write(f"   🔄 Removendo permissões de superuser...")
                old_admin.is_superuser = False
                old_admin.is_staff = False
                old_admin.is_active = False  # Desativar ao invés de deletar
                old_admin.save()
                self.stdout.write(self.style.SUCCESS(f"   ✅ Usuário {OLD_ADMIN_EMAIL} desativado"))
                self.stdout.write(f"      - is_superuser: {old_admin.is_superuser}")
                self.stdout.write(f"      - is_staff: {old_admin.is_staff}")
                self.stdout.write(f"      - is_active: {old_admin.is_active}")
        else:
            self.stdout.write(self.style.SUCCESS(f"   ✅ Usuário {OLD_ADMIN_EMAIL} não existe"))
        
        # 4. Resumo final
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS("✅ CORREÇÃO CONCLUÍDA!"))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"\n📋 Admin do sistema:")
        self.stdout.write(f"   Email: {correct_admin.email}")
        self.stdout.write(f"   Nome: {correct_admin.get_full_name()}")
        self.stdout.write(f"   Tenant: {correct_admin.tenant.name if correct_admin.tenant else 'N/A'}")
        self.stdout.write(f"   Permissões: Superuser ✅ | Staff ✅ | Active ✅")
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Agora você pode acessar com {CORRECT_ADMIN_EMAIL}"))

