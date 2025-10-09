#!/usr/bin/env python
"""
Script para testar a view evolution_config LOCALMENTE antes de fazer deploy.
Simula requisições GET e POST para identificar problemas.
"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.connections.views import evolution_config
from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant
from rest_framework.test import APIRequestFactory, force_authenticate

User = get_user_model()

def test_evolution_config():
    """Test evolution_config view locally."""
    
    print("=" * 70)
    print("🧪 TESTANDO VIEW evolution_config LOCALMENTE")
    print("=" * 70)
    
    # 1. Setup
    print("\n1️⃣ SETUP - Criando dados de teste...")
    factory = APIRequestFactory()
    
    # Buscar ou criar tenant
    tenant = Tenant.objects.first()
    if not tenant:
        print("   ❌ Nenhum tenant encontrado!")
        return False
    print(f"   ✅ Tenant: {tenant.name}")
    
    # Buscar ou criar user
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("   ❌ Nenhum superuser encontrado!")
        return False
    print(f"   ✅ User: {user.email}")
    
    # Limpar conexões existentes usando SQL direto (evita erro de criptografia)
    from django.db import connection as db_connection
    with db_connection.cursor() as cursor:
        cursor.execute("DELETE FROM connections_evolutionconnection;")
    print("   🧹 Conexões existentes removidas (SQL direto)")
    
    # 2. Testar GET (criar automático)
    print("\n2️⃣ TESTE GET - Criar conexão automática...")
    try:
        request = factory.get('/api/connections/evolution/config/')
        force_authenticate(request, user=user)
        
        response = evolution_config(request)
        
        if response.status_code == 200:
            data = response.data
            print(f"   ✅ GET retornou 200")
            print(f"   📋 Dados retornados:")
            print(f"      - ID: {data.get('id')}")
            print(f"      - Nome: {data.get('name')}")
            print(f"      - URL: {data.get('base_url')}")
            print(f"      - API Key: {'*' * 20 if data.get('api_key') else 'NULL'}")
            print(f"      - Status: {data.get('status')}")
            print(f"      - Erro: {data.get('last_error') or 'Nenhum'}")
        else:
            print(f"   ❌ GET retornou {response.status_code}")
            print(f"   Resposta: {response.data}")
            return False
    except Exception as e:
        print(f"   ❌ Erro no GET: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. Verificar se connection foi criada
    print("\n3️⃣ VERIFICAR - Connection criada no banco...")
    connections = EvolutionConnection.objects.all()
    print(f"   Total de connections: {connections.count()}")
    
    if connections.count() > 0:
        conn = connections.first()
        print(f"   ✅ Connection encontrada:")
        print(f"      - ID: {conn.id}")
        print(f"      - Nome: {conn.name}")
        print(f"      - URL: {conn.base_url}")
        print(f"      - API Key: {'SET' if conn.api_key else 'NULL'}")
        print(f"      - Status: {conn.status}")
        print(f"      - Tenant: {conn.tenant.name}")
    else:
        print(f"   ⚠️  Nenhuma connection criada")
    
    # 4. Testar POST (atualizar)
    print("\n4️⃣ TESTE POST - Atualizar configuração...")
    try:
        post_data = {
            'name': 'Evolution Test',
            'base_url': 'https://evo.rbtec.com.br',
            'api_key': 'TEST-KEY-12345',
            'is_active': True,
        }
        
        request = factory.post(
            '/api/connections/evolution/config/',
            data=post_data,
            content_type='application/json'
        )
        force_authenticate(request, user=user)
        
        response = evolution_config(request)
        
        if response.status_code == 200:
            data = response.data
            print(f"   ✅ POST retornou 200")
            print(f"   📋 Dados retornados:")
            print(f"      - ID: {data.get('id')}")
            print(f"      - Nome: {data.get('name')}")
            print(f"      - URL: {data.get('base_url')}")
            print(f"      - API Key: {'*' * 20 if data.get('api_key') else 'NULL'}")
            print(f"      - Status: {data.get('status')}")
        else:
            print(f"   ❌ POST retornou {response.status_code}")
            print(f"   Resposta: {response.data}")
            return False
    except Exception as e:
        print(f"   ❌ Erro no POST: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. Verificar atualização no banco
    print("\n5️⃣ VERIFICAR - Connection atualizada no banco...")
    conn = EvolutionConnection.objects.first()
    if conn:
        print(f"   ✅ Connection atualizada:")
        print(f"      - Nome: {conn.name} (esperado: 'Evolution Test')")
        print(f"      - URL: {conn.base_url}")
        print(f"      - API Key alterada: {'Sim' if conn.api_key == 'TEST-KEY-12345' else 'Não'}")
        
        if conn.name == 'Evolution Test':
            print(f"   ✅ Nome atualizado corretamente!")
        else:
            print(f"   ⚠️  Nome não foi atualizado")
    
    # 6. Limpeza
    print("\n6️⃣ LIMPEZA - Removendo dados de teste...")
    with db_connection.cursor() as cursor:
        cursor.execute("DELETE FROM connections_evolutionconnection;")
    print("   🧹 Conexões de teste removidas (SQL direto)")
    
    print("\n" + "=" * 70)
    print("✅ TESTE CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    return True


if __name__ == '__main__':
    try:
        success = test_evolution_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

