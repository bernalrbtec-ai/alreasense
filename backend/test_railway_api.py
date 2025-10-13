#!/usr/bin/env python
"""
Script para testar a API do Railway e verificar se os novos campos estão sendo retornados
"""
import requests
import json

def test_railway_api():
    """Testa a API do Railway para verificar os novos campos"""
    
    # URL da API do Railway
    url = "https://alreasense-backend-production.up.railway.app/api/campaigns/campaigns/"
    
    print("🔍 Testando API do Railway...")
    print(f"URL: {url}")
    
    try:
        # Fazer requisição GET
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verificar se há resultados
            if 'results' in data and len(data['results']) > 0:
                campaign = data['results'][0]  # Pegar primeira campanha
                
                print("\n📊 Primeira campanha encontrada:")
                print(f"Nome: {campaign.get('name', 'N/A')}")
                print(f"Status: {campaign.get('status', 'N/A')}")
                
                # Verificar campos novos
                print("\n🔍 Verificando novos campos:")
                print(f"last_contact_name: {campaign.get('last_contact_name', 'NÃO ENCONTRADO')}")
                print(f"last_contact_phone: {campaign.get('last_contact_phone', 'NÃO ENCONTRADO')}")
                print(f"last_instance_name: {campaign.get('last_instance_name', 'NÃO ENCONTRADO')}")
                print(f"next_contact_name: {campaign.get('next_contact_name', 'NÃO ENCONTRADO')}")
                print(f"next_contact_phone: {campaign.get('next_contact_phone', 'NÃO ENCONTRADO')}")
                print(f"next_instance_name: {campaign.get('next_instance_name', 'NÃO ENCONTRADO')}")
                
                # Verificar se os campos estão presentes na resposta
                missing_fields = []
                required_fields = ['last_instance_name']
                
                for field in required_fields:
                    if field not in campaign:
                        missing_fields.append(field)
                
                if missing_fields:
                    print(f"\n❌ Campos faltando: {missing_fields}")
                    print("   Isso indica que a migration não foi aplicada no Railway")
                else:
                    print("\n✅ Todos os campos novos estão presentes!")
                    
            else:
                print("❌ Nenhuma campanha encontrada na resposta")
                print(f"Resposta completa: {json.dumps(data, indent=2)}")
                
        else:
            print(f"❌ Erro na API: {response.status_code}")
            print(f"Resposta: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro ao fazer requisição: {e}")

if __name__ == "__main__":
    test_railway_api()
