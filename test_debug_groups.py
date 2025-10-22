"""
Script para testar endpoint de debug de grupos.
Executa automaticamente e salva resultados.
"""
import requests
import json
import sys

# Configurações
API_URL = "https://alreasense-backend-production.up.railway.app"
EMAIL = "paulo.bernal@rbtec.com.br"
PASSWORD = "Paulo@2508"
TIMEOUT = 60  # 60 segundos

def main():
    print("🔐 Fazendo login...")
    
    try:
        # 1. Login
        login_response = requests.post(
            f"{API_URL}/api/auth/login/",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=TIMEOUT
        )
        
        if login_response.status_code != 200:
            print(f"❌ Erro no login: {login_response.status_code}")
            print(login_response.text)
            sys.exit(1)
        
        token = login_response.json()["access"]
        print(f"✅ Login OK! Token: {token[:30]}...")
        
        # 2. Buscar grupos (debug endpoint)
        print("\n🔍 Buscando grupos da instância Evolution...")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        groups_response = requests.get(
            f"{API_URL}/api/chat/conversations/debug_list_groups/",
            headers=headers,
            timeout=TIMEOUT
        )
        
        if groups_response.status_code != 200:
            print(f"❌ Erro ao buscar grupos: {groups_response.status_code}")
            print(groups_response.text)
            sys.exit(1)
        
        data = groups_response.json()
        
        print(f"\n✅ {data['total_groups']} grupos encontrados!")
        print(f"   Instância: {data['instance']}")
        
        # 3. Mostrar grupos
        print("\n📋 LISTA DE GRUPOS:")
        print("=" * 80)
        
        for i, group in enumerate(data['groups'], 1):
            print(f"\n{i}. {group['subject']}")
            print(f"   ID: {group['id']}")
            print(f"   Participantes: {group['participants_count']}")
            print(f"   Owner: {group.get('owner', 'N/A')}")
        
        # 4. Salvar resultado completo
        output_file = "debug_groups_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultado completo salvo em: {output_file}")
        
        # 5. Buscar grupos problemáticos
        print("\n🔍 VERIFICANDO GRUPOS PROBLEMÁTICOS:")
        print("=" * 80)
        
        problematic_jids = [
            "1387239175@g.us",
            "1607948593@g.us",
        ]
        
        found_jids = [g['id'] for g in data['groups']]
        
        for jid in problematic_jids:
            if jid in found_jids:
                group = next(g for g in data['groups'] if g['id'] == jid)
                print(f"✅ {jid} ENCONTRADO: {group['subject']}")
            else:
                print(f"❌ {jid} NÃO ENCONTRADO (grupo deletado ou instância saiu)")
        
        print("\n" + "=" * 80)
        print("✅ TESTE CONCLUÍDO!")
        
    except requests.exceptions.Timeout:
        print("❌ Timeout na requisição (servidor demorou mais de 60s)")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro na requisição: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

