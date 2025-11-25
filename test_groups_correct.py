"""
Teste final com o endpoint correto.
"""
import requests
import json

EVO_BASE_URL = "https://evo.rbtec.com.br"
EVO_API_KEY = "584B4A4A-0815-AC86-DC39-C38FC27E8E17"
INSTANCE_NAME = "0cd3505a-c6e5-454d-9f88-e66c41e8761f"

headers = {
    "apikey": EVO_API_KEY,
    "Content-Type": "application/json"
}

# Endpoint CORRETO
endpoint = f"{EVO_BASE_URL}/group/fetchAllGroups/{INSTANCE_NAME}"
params = {'getParticipants': 'false'}

print("🔍 Testando endpoint CORRETO com getParticipants")
print(f"   URL: {endpoint}")
print(f"   Params: {params}")

response = requests.get(endpoint, headers=headers, params=params, timeout=10)

print(f"\n✅ Status: {response.status_code}")

if response.status_code == 200:
    groups = response.json()
    print(f"✅ {len(groups)} grupos encontrados!\n")
    
    # Mostrar todos os grupos
    for i, group in enumerate(groups, 1):
        print(f"{i}. {group.get('subject', 'Sem nome')} - {group.get('id', 'N/A')}")
        print(f"   Participantes: {group.get('size', 0)}")
    
    # Salvar
    with open('groups_final_result.json', 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Resultado salvo em: groups_final_result.json")
    
    # Verificar grupos problemáticos
    print("\n🔍 VERIFICANDO GRUPOS PROBLEMÁTICOS:")
    print("=" * 80)
    problematic_jids = ["1387239175@g.us", "1607948593@g.us"]
    found_jids = [g['id'] for g in groups]
    
    for jid in problematic_jids:
        if jid in found_jids:
            group = next(g for g in groups if g['id'] == jid)
            print(f"✅ {jid} ENCONTRADO!")
            print(f"   Nome: {group.get('subject', 'N/A')}")
            print(f"   Participantes: {group.get('size', 0)}")
        else:
            print(f"❌ {jid} NÃO ENCONTRADO")
            print(f"   → Grupo foi deletado ou instância saiu do grupo")
else:
    print(f"❌ Erro: {response.status_code}")
    print(response.text)





































