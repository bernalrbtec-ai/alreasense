"""
Script de teste completo para o módulo de Contatos
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def login():
    """Faz login e retorna o token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login/",
        json={
            "email": "superadmin@alreasense.com",
            "password": "admin123"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Login realizado: {data['user']['email']}")
        return data['access']
    else:
        print(f"❌ Erro no login: {response.status_code}")
        print(response.text)
        return None

def test_create_contact(token):
    """Testa criação de contato"""
    print("\n📝 Testando criação de contato...")
    
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "Maria Silva",
        "phone": "+5511999999999",
        "email": "maria@example.com",
        "city": "São Paulo",
        "state": "SP",
        "birth_date": "1990-05-15",
        "notes": "Cliente VIP de teste"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/contacts/contacts/",
        headers=headers,
        json=data
    )
    
    if response.status_code == 201:
        contact = response.json()
        print(f"✅ Contato criado: {contact['name']} ({contact['id']})")
        print(f"   Lifecycle: {contact['lifecycle_stage']}")
        print(f"   Engagement: {contact['engagement_score']}/100")
        return contact['id']
    else:
        print(f"❌ Erro ao criar contato: {response.status_code}")
        print(response.text)
        return None

def test_list_contacts(token):
    """Testa listagem de contatos"""
    print("\n📋 Testando listagem de contatos...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/contacts/contacts/",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        contacts = data.get('results', data)
        print(f"✅ {len(contacts)} contato(s) encontrado(s)")
        
        for contact in contacts[:3]:  # Mostrar apenas os 3 primeiros
            print(f"   - {contact['name']}: {contact['phone']}")
        
        return len(contacts)
    else:
        print(f"❌ Erro ao listar contatos: {response.status_code}")
        return 0

def test_search_contacts(token):
    """Testa busca de contatos"""
    print("\n🔍 Testando busca de contatos...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/contacts/contacts/?search=Maria",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        contacts = data.get('results', data)
        print(f"✅ Busca por 'Maria': {len(contacts)} resultado(s)")
        return True
    else:
        print(f"❌ Erro na busca: {response.status_code}")
        return False

def test_insights(token):
    """Testa endpoint de insights"""
    print("\n📊 Testando insights...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/contacts/contacts/insights/",
        headers=headers
    )
    
    if response.status_code == 200:
        insights = response.json()
        print(f"✅ Insights obtidos:")
        print(f"   Total: {insights['total_contacts']}")
        print(f"   Leads: {insights['lifecycle_breakdown']['lead']}")
        print(f"   Customers: {insights['lifecycle_breakdown']['customer']}")
        print(f"   LTV Médio: R$ {insights['average_ltv']:.2f}")
        return True
    else:
        print(f"❌ Erro ao obter insights: {response.status_code}")
        return False

def test_create_tag(token):
    """Testa criação de tag"""
    print("\n🏷️  Testando criação de tag...")
    
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "VIP",
        "color": "#FFD700",
        "description": "Clientes VIP"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/contacts/tags/",
        headers=headers,
        json=data
    )
    
    if response.status_code == 201:
        tag = response.json()
        print(f"✅ Tag criada: {tag['name']} (#{tag['color']})")
        return tag['id']
    else:
        print(f"❌ Erro ao criar tag: {response.status_code}")
        print(response.text)
        return None

def test_product_access(token):
    """Testa acesso ao produto contacts"""
    print("\n🔐 Testando acesso ao produto...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Verificar limites
    response = requests.get(
        f"{BASE_URL}/api/tenants/tenants/limits/",
        headers=headers
    )
    
    if response.status_code == 200:
        limits = response.json()
        print(f"✅ Limites obtidos:")
        
        if 'products' in limits and 'contacts' in limits['products']:
            contacts_limit = limits['products']['contacts']
            print(f"   Contacts disponível: {contacts_limit.get('is_active', False)}")
            print(f"   Limite: {contacts_limit.get('limit', 'N/A')}")
        else:
            print(f"   ⚠️  Produto 'contacts' não encontrado nos limites")
        
        return True
    else:
        print(f"❌ Erro ao verificar limites: {response.status_code}")
        return False

def run_all_tests():
    """Executa todos os testes"""
    print("🚀 Iniciando testes do módulo Contacts\n")
    print("="*60)
    
    # Login
    token = login()
    if not token:
        print("\n❌ Não foi possível realizar login. Abortando testes.")
        return
    
    # Testes
    results = {
        'product_access': test_product_access(token),
        'create_contact': test_create_contact(token),
        'list_contacts': test_list_contacts(token),
        'search_contacts': test_search_contacts(token),
        'insights': test_insights(token),
        'create_tag': test_create_tag(token)
    }
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 Todos os testes passaram!")
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")

if __name__ == '__main__':
    run_all_tests()


