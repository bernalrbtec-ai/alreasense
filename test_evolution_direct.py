"""
Script para testar diretamente a API Evolution e descobrir endpoints corretos.
"""
import requests
import json

# Configurações Evolution API
EVO_BASE_URL = "https://evo.rbtec.com.br"
EVO_API_KEY = "584B4A4A-0815-AC86-DC39-C38FC27E8E17"  # API key global
INSTANCE_NAME = "0cd3505a-c6e5-454d-9f88-e66c41e8761f"

headers = {
    "apikey": EVO_API_KEY,
    "Content-Type": "application/json"
}

print("🔍 TESTANDO ENDPOINTS DA EVOLUTION API")
print("=" * 80)

# Lista de endpoints para testar
endpoints_to_test = [
    # Formato 1: Com instance no path
    f"/group/fetchAllGroups/{INSTANCE_NAME}",
    
    # Formato 2: Sem instance no path (instance vai na apikey)
    "/group/fetchAllGroups",
    
    # Formato 3: Com query param
    f"/group/fetchAllGroups?instance={INSTANCE_NAME}",
    
    # Formato 4: V2 API
    f"/v2/group/fetchAllGroups/{INSTANCE_NAME}",
    
    # Formato 5: Listar instâncias primeiro
    "/instance/fetchInstances",
]

for endpoint in endpoints_to_test:
    url = f"{EVO_BASE_URL}{endpoint}"
    print(f"\n📍 Testando: {endpoint}")
    print(f"   URL completa: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list):
                print(f"   ✅ SUCESSO! Retornou lista com {len(data)} itens")
                
                # Se for lista de grupos, mostrar o primeiro
                if len(data) > 0 and 'id' in data[0]:
                    print(f"   Primeiro grupo: {data[0].get('id', 'N/A')} - {data[0].get('subject', 'N/A')}")
                    
                    # Salvar resultado completo
                    with open('evolution_groups_result.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"   💾 Resultado completo salvo em: evolution_groups_result.json")
                    
                    # Buscar os grupos problemáticos
                    print(f"\n   🔍 VERIFICANDO GRUPOS PROBLEMÁTICOS:")
                    problematic_jids = ["1387239175@g.us", "1607948593@g.us"]
                    found_jids = [g['id'] for g in data if 'id' in g]
                    
                    for jid in problematic_jids:
                        if jid in found_jids:
                            group = next(g for g in data if g['id'] == jid)
                            print(f"   ✅ {jid} ENCONTRADO: {group.get('subject', 'N/A')}")
                        else:
                            print(f"   ❌ {jid} NÃO ENCONTRADO")
            else:
                print(f"   Resposta (primeiros 200 chars): {str(data)[:200]}")
        elif response.status_code == 404:
            print(f"   ❌ 404 Not Found")
        else:
            print(f"   ❌ Erro: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except requests.exceptions.Timeout:
        print(f"   ⏰ Timeout (10s)")
    except Exception as e:
        print(f"   ❌ Exceção: {e}")

print("\n" + "=" * 80)
print("✅ TESTES CONCLUÍDOS!")










