#!/usr/bin/env python
"""
Script para verificar se existe EvolutionConnection no banco
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.connections.models import EvolutionConnection

def check_evolution_connections():
    print("=" * 60)
    print("🔍 VERIFICANDO EVOLUTION CONNECTIONS NO BANCO")
    print("=" * 60)
    
    connections = EvolutionConnection.objects.all()
    
    print(f"📊 Total de registros: {connections.count()}")
    
    for conn in connections:
        print(f"\n✅ Connection ID: {conn.id}")
        print(f"   - Nome: {conn.name}")
        print(f"   - URL: {conn.base_url}")
        print(f"   - API Key: {'CONFIGURADA' if conn.api_key else 'NÃO CONFIGURADA'}")
        print(f"   - Ativo: {conn.is_active}")
        print(f"   - Status: {conn.status}")
        print(f"   - Tenant: {conn.tenant.name if conn.tenant else 'Nenhum'}")
    
    if connections.count() == 0:
        print("\n❌ NENHUM REGISTRO ENCONTRADO!")
        print("   O servidor está sendo salvo hardcoded na view, não no banco!")
        print("   Precisamos criar um registro na tabela EvolutionConnection")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    check_evolution_connections()
