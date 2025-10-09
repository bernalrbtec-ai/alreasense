#!/usr/bin/env python
"""
Script para simular a chamada da view evolution_config e criar o registro
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

def simulate_evolution_config():
    print("=" * 60)
    print("🔧 SIMULANDO EVOLUTION CONFIG PARA CRIAR REGISTRO")
    print("=" * 60)
    
    # Buscar tenant
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado!")
        return
    
    print(f"✅ Tenant: {tenant.name}")
    
    # Simular a lógica da view GET
    connection = EvolutionConnection.objects.filter(is_active=True).first()
    
    if not connection:
        print("📝 Criando EvolutionConnection...")
        connection = EvolutionConnection.objects.create(
            tenant=tenant,
            name='Evolution RBTec',
            base_url='https://evo.rbtec.com.br',
            api_key='584B4A4A-0815-AC86-DC39-C38FC27E8E17',
            is_active=True,
            status='inactive'
        )
        print(f"✅ EvolutionConnection criada: {connection.id}")
    else:
        print(f"✅ EvolutionConnection já existe: {connection.id}")
    
    print(f"\n📋 Detalhes:")
    print(f"   - ID: {connection.id}")
    print(f"   - Nome: {connection.name}")
    print(f"   - URL: {connection.base_url}")
    print(f"   - API Key: {'CONFIGURADA' if connection.api_key else 'NÃO CONFIGURADA'}")
    print(f"   - Ativo: {connection.is_active}")
    print(f"   - Status: {connection.status}")
    
    return connection

if __name__ == '__main__':
    simulate_evolution_config()
