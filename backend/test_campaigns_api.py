#!/usr/bin/env python
"""
Teste completo da API de Campanhas
Testa criação, listagem, logs e funcionalidades
"""
import requests
import json

BASE_URL = 'http://localhost:8000'

def test_campaigns_api():
    print("\n" + "="*70)
    print("🧪 TESTE - API DE CAMPANHAS")
    print("="*70)
    
    # 1. Login
    print("\n1️⃣ Login como teste@campanhas.com")
    login_response = requests.post(
        f'{BASE_URL}/api/auth/login/',
        json={
            'email': 'teste@campanhas.com',
            'password': 'teste123'
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Erro no login: {login_response.status_code}")
        print(login_response.text)
        return
    
    token = login_response.json()['access']
    user = login_response.json()['user']
    print(f"✅ Login bem-sucedido!")
    print(f"   Tenant: {user['tenant']['name']}")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    # 2. Listar Campanhas
    print("\n2️⃣ Listando campanhas existentes")
    list_response = requests.get(
        f'{BASE_URL}/api/campaigns/campaigns/',
        headers=headers
    )
    
    print(f"Status: {list_response.status_code}")
    campaigns = list_response.json().get('results', [])
    print(f"Total de campanhas: {len(campaigns)}")
    
    # 3. Listar Instâncias disponíveis
    print("\n3️⃣ Listando instâncias de WhatsApp")
    instances_response = requests.get(
        f'{BASE_URL}/api/notifications/whatsapp-instances/',
        headers=headers
    )
    
    instances = instances_response.json().get('results', [])
    print(f"Total de instâncias: {len(instances)}")
    
    if len(instances) > 0:
        for inst in instances:
            print(f"   - {inst['friendly_name']} (Health: {inst['health_score']}) - {inst['connection_state']}")
    
    # 4. Listar Listas de Contatos
    print("\n4️⃣ Listando listas de contatos")
    try:
        contacts_response = requests.get(
            f'{BASE_URL}/api/contacts/contact-lists/',
            headers=headers
        )
        
        if contacts_response.status_code == 200:
            contact_lists = contacts_response.json().get('results', [])
            print(f"Total de listas: {len(contact_lists)}")
            
            if len(contact_lists) > 0:
                for cl in contact_lists:
                    print(f"   - {cl['name']} ({cl['contact_count']} contatos)")
        else:
            print(f"⚠️ Erro ao buscar listas: {contacts_response.status_code}")
            contact_lists = []
    except Exception as e:
        print(f"⚠️ Erro ao buscar listas: {e}")
        contact_lists = []
    
    # 5. Criar Campanha de Teste (se houver instâncias)
    if len(instances) > 0:
        print("\n5️⃣ Criando campanha de teste")
        
        campaign_data = {
            'name': 'Campanha Teste - API',
            'description': 'Teste de criação via API com sistema de logs',
            'rotation_mode': 'intelligent',
            'instances': [inst['id'] for inst in instances[:2]],  # Primeiras 2 instâncias
            'interval_min': 3,
            'interval_max': 8,
            'daily_limit_per_instance': 100,
            'pause_on_health_below': 50,
            'messages': [
                {
                    'content': 'Olá! Esta é uma mensagem de teste da campanha.',
                    'order': 1
                },
                {
                    'content': 'Mensagem de teste #2 - Variação para evitar banimento.',
                    'order': 2
                }
            ]
        }
        
        create_response = requests.post(
            f'{BASE_URL}/api/campaigns/campaigns/',
            headers=headers,
            json=campaign_data
        )
        
        print(f"Status: {create_response.status_code}")
        
        if create_response.status_code == 201:
            campaign = create_response.json()
            print(f"✅ Campanha criada com sucesso!")
            print(f"   ID: {campaign['id']}")
            print(f"   Nome: {campaign['name']}")
            print(f"   Modo de Rotação: {campaign['rotation_mode_display']}")
            print(f"   Instâncias: {len(campaign['instances'])}")
            print(f"   Mensagens: {len(campaign['messages'])}")
            
            campaign_id = campaign['id']
            
            # 6. Verificar Logs da Campanha
            print("\n6️⃣ Verificando logs da campanha")
            logs_response = requests.get(
                f'{BASE_URL}/api/campaigns/campaigns/{campaign_id}/logs/',
                headers=headers
            )
            
            logs = logs_response.json()
            print(f"Total de logs: {len(logs)}")
            
            if len(logs) > 0:
                print("\n📋 Logs da Campanha:")
                for log in logs[:5]:  # Primeiros 5
                    print(f"   [{log['severity_display']}] {log['log_type_display']}: {log['message']}")
                    if log['details']:
                        print(f"      Detalhes: {json.dumps(log['details'], indent=10)}")
            
            # 7. Testar Stats
            print("\n7️⃣ Estatísticas gerais de campanhas")
            stats_response = requests.get(
                f'{BASE_URL}/api/campaigns/campaigns/stats/',
                headers=headers
            )
            
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"✅ Estatísticas:")
                print(f"   Total de campanhas: {stats['total_campaigns']}")
                print(f"   Campanhas ativas: {stats['active_campaigns']}")
                print(f"   Campanhas concluídas: {stats['completed_campaigns']}")
                print(f"   Total de mensagens enviadas: {stats['total_messages_sent']}")
        else:
            print(f"❌ Erro ao criar campanha: {create_response.text}")
    
    print("\n" + "="*70)
    print("✅ TESTE CONCLUÍDO!")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_campaigns_api()

