"""
Script para buscar o nome real da instância na Evolution API
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

import httpx
from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant

print("🔍 Buscando nome real da instância na Evolution API...")
print("=" * 60)

rbtec = Tenant.objects.get(name="RBTec Informática")
conn = EvolutionConnection.objects.filter(tenant=rbtec, is_active=True).first()

print(f"📱 Conexão:")
print(f"   Nome amigável: '{conn.name}'")
print(f"   Base URL: {conn.base_url}")
print(f"   API Key: {conn.api_key[:15]}...")

# Buscar instâncias na Evolution API
try:
    url = f"{conn.base_url}/instance/fetchInstances"
    headers = {
        'apikey': conn.api_key
    }
    
    print(f"\n🌐 Consultando Evolution API...")
    print(f"   URL: {url}")
    
    response = httpx.get(url, headers=headers, timeout=10.0)
    response.raise_for_status()
    
    data = response.json()
    print(f"\n✅ Resposta recebida!")
    print(f"\n📱 Total de instâncias: {len(data)}")
    
    print("\n" + "=" * 60)
    print("🔍 Procurando instância conectada do RBTec...")
    print("=" * 60)
    
    rbtec_instance = None
    
    for instance in data:
        status = instance.get('connectionStatus')
        profile = instance.get('profileName', '')
        owner = instance.get('ownerJid', '')
        name = instance.get('name', '')
        
        print(f"\n📱 {profile or owner}")
        print(f"   Nome técnico: {name}")
        print(f"   Status: {status}")
        
        # Se for a instância do Paulo (RBTec)
        if '+5517991253112' in owner or 'paulo' in profile.lower() or 'rbtec' in profile.lower():
            print(f"   ⭐ ESTA É A INSTÂNCIA DO RBTEC!")
            rbtec_instance = instance
    
    if rbtec_instance:
        print("\n" + "=" * 60)
        print("🎯 INSTÂNCIA ENCONTRADA!")
        print("=" * 60)
        print(f"Nome técnico: {rbtec_instance['name']}")
        print(f"Status: {rbtec_instance['connectionStatus']}")
        print(f"Profile: {rbtec_instance['profileName']}")
        print(f"Telefone: {rbtec_instance['ownerJid']}")
        
        print("\n✅ URL correta da Evolution API:")
        print(f"{conn.base_url}/message/sendText/{rbtec_instance['name']}")
    else:
        print("\n❌ Instância do RBTec não encontrada automaticamente.")
        print("Verifique manualmente qual instância você quer usar.")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"\n❌ Erro ao consultar Evolution API: {e}")
    print("\nAlternativa: Verifique no painel da Evolution API qual é o nome técnico da instância.")

