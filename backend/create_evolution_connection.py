#!/usr/bin/env python
"""
Script para criar EvolutionConnection no banco com os dados hardcoded
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

def create_evolution_connection():
    print("=" * 60)
    print("🔧 CRIANDO EVOLUTION CONNECTION NO BANCO")
    print("=" * 60)
    
    # Buscar tenant padrão
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado!")
        return
    
    print(f"✅ Tenant: {tenant.name}")
    
    # Dados hardcoded da view
    base_url = 'https://evo.rbtec.com.br'
    api_key = '584B4A4A-0815-AC86-DC39-C38FC27E8E17'
    
    # Verificar se já existe
    existing = EvolutionConnection.objects.filter(
        base_url=base_url,
        tenant=tenant
    ).first()
    
    if existing:
        print(f"✅ EvolutionConnection já existe: {existing.name}")
        print(f"   - Ativo: {existing.is_active}")
        print(f"   - Status: {existing.status}")
        return existing
    
    # Criar novo registro
    try:
        connection = EvolutionConnection.objects.create(
            tenant=tenant,
            name="Evolution RBTec",
            base_url=base_url,
            api_key=api_key,
            is_active=True,
            status='active'
        )
        
        print(f"✅ EvolutionConnection criada com sucesso!")
        print(f"   - ID: {connection.id}")
        print(f"   - Nome: {connection.name}")
        print(f"   - URL: {connection.base_url}")
        print(f"   - API Key: {'CONFIGURADA' if connection.api_key else 'NÃO CONFIGURADA'}")
        print(f"   - Ativo: {connection.is_active}")
        print(f"   - Status: {connection.status}")
        
        return connection
        
    except Exception as e:
        print(f"❌ Erro ao criar EvolutionConnection: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    create_evolution_connection()
