"""
Comando para configurar o sistema de billing
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = 'Configura o sistema de billing completo'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Configurando sistema de billing...')
        
        # 1. Criar tabelas do billing
        self.stdout.write('📋 Criando tabelas do billing...')
        try:
            call_command('migrate', 'billing', verbosity=0)
            self.stdout.write('  ✅ Tabelas criadas')
        except Exception as e:
            self.stdout.write(f'  ❌ Erro ao criar tabelas: {e}')
            return
        
        # 2. Popular dados iniciais
        self.stdout.write('🌱 Populando dados iniciais...')
        try:
            call_command('seed_products', verbosity=0)
            self.stdout.write('  ✅ Dados iniciais criados')
        except Exception as e:
            self.stdout.write(f'  ❌ Erro ao popular dados: {e}')
            return
        
        # 3. Verificar se tudo está funcionando
        self.stdout.write('🔍 Verificando configuração...')
        try:
            from apps.billing.models import Product, Plan
            products_count = Product.objects.count()
            plans_count = Plan.objects.count()
            
            self.stdout.write(f'  📦 Produtos: {products_count}')
            self.stdout.write(f'  💳 Planos: {plans_count}')
            
            if products_count > 0 and plans_count > 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Sistema de billing configurado com sucesso!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Sistema não foi configurado corretamente')
                )
                
        except Exception as e:
            self.stdout.write(f'  ❌ Erro na verificação: {e}')
