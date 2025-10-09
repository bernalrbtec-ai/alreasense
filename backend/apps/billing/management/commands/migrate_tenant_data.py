"""
Comando para migrar dados existentes do Tenant para nova estrutura
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.tenancy.models import Tenant
from apps.billing.models import Plan, TenantProduct, Product


class Command(BaseCommand):
    help = 'Migra dados existentes do Tenant para nova estrutura de produtos'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Iniciando migração de dados do Tenant...')
        
        with transaction.atomic():
            # Primeiro, criar planos básicos se não existirem
            self.create_basic_plans()
            
            # Migrar tenants existentes
            self.migrate_tenants()
            
        self.stdout.write(
            self.style.SUCCESS('✅ Migração concluída com sucesso!')
        )

    def create_basic_plans(self):
        """Cria planos básicos se não existirem"""
        self.stdout.write('💳 Criando planos básicos...')
        
        plans_data = [
            {
                'slug': 'starter',
                'name': 'Starter',
                'description': 'Plano básico migrado',
                'price': 49.00,
                'color': '#3B82F6',
                'sort_order': 1,
            },
            {
                'slug': 'pro',
                'name': 'Pro',
                'description': 'Plano profissional migrado',
                'price': 149.00,
                'color': '#8B5CF6',
                'sort_order': 2,
            },
            {
                'slug': 'api_only',
                'name': 'API Only',
                'description': 'Plano apenas API migrado',
                'price': 99.00,
                'color': '#F59E0B',
                'sort_order': 3,
            },
            {
                'slug': 'enterprise',
                'name': 'Enterprise',
                'description': 'Plano enterprise migrado',
                'price': 499.00,
                'color': '#EF4444',
                'sort_order': 4,
                'is_enterprise': True,
            },
        ]
        
        for data in plans_data:
            plan, created = Plan.objects.get_or_create(
                slug=data['slug'],
                defaults=data
            )
            status = 'criado' if created else 'já existe'
            self.stdout.write(f'  💳 {plan.name} - {status}')

    def migrate_tenants(self):
        """Migra tenants existentes"""
        self.stdout.write('🏢 Migrando tenants...')
        
        # Mapear planos antigos para novos
        plan_mapping = {
            'starter': 'starter',
            'pro': 'pro',
            'scale': 'pro',  # Scale vira Pro
            'enterprise': 'enterprise',
        }
        
        tenants = Tenant.objects.all()
        for tenant in tenants:
            self.stdout.write(f'  🏢 Migrando {tenant.name}...')
            
            # Mapear plano antigo para novo
            old_plan = tenant.plan
            new_plan_slug = plan_mapping.get(old_plan, 'starter')
            
            try:
                new_plan = Plan.objects.get(slug=new_plan_slug)
                tenant.current_plan = new_plan
                tenant.save()
                
                self.stdout.write(f'    ✅ Plano: {old_plan} → {new_plan.name}')
                
            except Plan.DoesNotExist:
                self.stdout.write(f'    ⚠️  Plano {new_plan_slug} não encontrado, mantendo sem plano')
        
        self.stdout.write(f'  📊 Total de tenants migrados: {tenants.count()}')
