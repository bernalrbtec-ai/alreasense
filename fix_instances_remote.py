"""
Script para analisar e corrigir instâncias Evolution/WhatsApp direto no Railway.
Conecta via URL pública do PostgreSQL.
"""
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

def connect_database(db_url):
    """Conecta no banco Railway."""
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        print("✅ Conectado ao banco Railway!")
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return None

def analyze_instances(conn):
    """Analisa instâncias no banco."""
    print("\n" + "="*80)
    print("📊 ANÁLISE COMPLETA DO BANCO")
    print("="*80)
    
    cursor = conn.cursor()
    
    # 1. Tenants
    print("\n📋 TENANTS:")
    cursor.execute("SELECT id, name FROM tenancy_tenant ORDER BY name")
    tenants = cursor.fetchall()
    for t in tenants:
        print(f"  - {t['name']} (ID: {t['id']})")
    
    # 2. WhatsApp Instances
    print("\n📱 WHATSAPP INSTANCES:")
    cursor.execute("""
        SELECT 
            w.id,
            w.friendly_name,
            w.instance_name,
            w.is_active,
            w.status,
            w.created_at,
            t.name as tenant_name
        FROM notifications_whatsappinstance w
        LEFT JOIN tenancy_tenant t ON w.tenant_id = t.id
        ORDER BY w.created_at
    """)
    
    instances = cursor.fetchall()
    
    active_count = 0
    inactive_count = 0
    
    for inst in instances:
        active_emoji = "✅" if inst['is_active'] else "❌"
        print(f"\n{active_emoji} {inst['friendly_name'] or '(sem nome)'}")
        print(f"  ID: {inst['id']}")
        print(f"  Instance name: {inst['instance_name'] or '(vazio)'}")
        print(f"  Tenant: {inst['tenant_name'] or 'Global'}")
        print(f"  Status: {inst['status']}")
        print(f"  Ativo: {inst['is_active']}")
        print(f"  Criado: {inst['created_at']}")
        
        if inst['is_active']:
            active_count += 1
        else:
            inactive_count += 1
    
    print(f"\n📊 RESUMO:")
    print(f"  ✅ Ativas: {active_count}")
    print(f"  ❌ Inativas: {inactive_count}")
    print(f"  📦 Total: {len(instances)}")
    
    # 3. Evolution Connections (se existir)
    try:
        cursor.execute("""
            SELECT 
                id, name, base_url, is_active, status, tenant_id
            FROM connections_evolutionconnection
            ORDER BY id
        """)
        connections = cursor.fetchall()
        
        if connections:
            print(f"\n🔌 EVOLUTION CONNECTIONS: {len(connections)}")
            for conn in connections:
                active_emoji = "✅" if conn['is_active'] else "❌"
                print(f"  {active_emoji} ID {conn['id']}: {conn['name'] or '(sem nome)'}")
    except:
        print("\n🔌 EVOLUTION CONNECTIONS: Tabela não existe ou vazia")
    
    return instances, tenants

def list_evolution_instances(api_url, api_key):
    """Lista instâncias na Evolution API."""
    print("\n" + "="*80)
    print("🔍 INSTÂNCIAS NA EVOLUTION API")
    print("="*80)
    
    try:
        response = requests.get(
            f"{api_url}/instance/fetchInstances",
            headers={'apikey': api_key},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Erro: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return []
        
        instances = response.json()
        print(f"\n✅ Encontradas {len(instances)} instâncias:\n")
        
        for idx, inst in enumerate(instances, 1):
            data = inst.get('instance', {})
            name = data.get('instanceName', 'N/A')
            uuid = data.get('instanceId', 'N/A')
            status = data.get('status', 'N/A')
            
            print(f"{idx}. {name}")
            print(f"   UUID: {uuid}")
            print(f"   Status: {status}\n")
        
        return instances
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []

def clean_inactive_instances(conn):
    """Remove instâncias inativas."""
    print("\n" + "="*80)
    print("🗑️  LIMPANDO INSTÂNCIAS INATIVAS")
    print("="*80)
    
    cursor = conn.cursor()
    
    # Contar inativas
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM notifications_whatsappinstance 
        WHERE is_active = false
    """)
    count = cursor.fetchone()['count']
    
    if count == 0:
        print("\n✅ Nenhuma instância inativa para deletar")
        return
    
    # Mostrar inativas
    cursor.execute("""
        SELECT w.id, w.friendly_name, t.name as tenant_name
        FROM notifications_whatsappinstance w
        LEFT JOIN tenancy_tenant t ON w.tenant_id = t.id
        WHERE w.is_active = false
    """)
    
    inactives = cursor.fetchall()
    print(f"\n⚠️  Encontradas {count} instâncias inativas:")
    for inst in inactives:
        print(f"  - {inst['friendly_name']} (Tenant: {inst['tenant_name'] or 'Global'})")
    
    confirm = input(f"\n❓ Deletar {count} instâncias? (digite 'SIM'): ")
    
    if confirm == 'SIM':
        cursor.execute("DELETE FROM notifications_whatsappinstance WHERE is_active = false")
        conn.commit()
        print(f"\n✅ {count} instâncias deletadas!")
    else:
        print("\n❌ Cancelado")

def update_active_instance(conn, evolution_instances, tenant_name='RBTec Informática'):
    """Atualiza instância ativa."""
    print("\n" + "="*80)
    print("🔧 ATUALIZANDO INSTÂNCIA ATIVA")
    print("="*80)
    
    cursor = conn.cursor()
    
    # Buscar tenant
    cursor.execute("SELECT id, name FROM tenancy_tenant WHERE name = %s", (tenant_name,))
    tenant = cursor.fetchone()
    
    if not tenant:
        print(f"❌ Tenant '{tenant_name}' não encontrado!")
        return
    
    # Buscar instância ativa
    cursor.execute("""
        SELECT id, friendly_name, instance_name
        FROM notifications_whatsappinstance
        WHERE tenant_id = %s AND is_active = true
        LIMIT 1
    """, (tenant['id'],))
    
    active = cursor.fetchone()
    
    if not active:
        print(f"❌ Nenhuma instância ativa para {tenant_name}")
        return
    
    print(f"\n📋 Instância ativa:")
    print(f"  ID: {active['id']}")
    print(f"  Nome: {active['friendly_name']}")
    print(f"  Instance name: {active['instance_name']}")
    
    if not evolution_instances:
        print("\n⚠️  Sem instâncias da Evolution API")
        return
    
    # Escolher instância
    print(f"\n📋 Escolha instância Evolution:")
    for idx, inst in enumerate(evolution_instances, 1):
        data = inst.get('instance', {})
        name = data.get('instanceName', 'N/A')
        uuid = data.get('instanceId', 'N/A')
        status = data.get('status', 'N/A')
        
        print(f"\n{idx}. {name}")
        print(f"   UUID: {uuid}")
        print(f"   Status: {status}")
    
    try:
        choice = int(input(f"\n❓ Número (1-{len(evolution_instances)}): ")) - 1
        
        if choice < 0 or choice >= len(evolution_instances):
            print("❌ Inválido!")
            return
        
        selected = evolution_instances[choice]
        data = selected.get('instance', {})
        new_name = data.get('instanceName')
        new_uuid = data.get('instanceId')
        
        print(f"\n✅ Selecionado:")
        print(f"  Nome: {new_name}")
        print(f"  UUID: {new_uuid}")
        
        print(f"\n🔄 Mudanças:")
        print(f"  Nome: '{active['friendly_name']}' → '{new_name}'")
        print(f"  UUID: '{active['instance_name']}' → '{new_uuid}'")
        
        confirm = input(f"\n❓ Confirmar? (SIM): ")
        
        if confirm == 'SIM':
            cursor.execute("""
                UPDATE notifications_whatsappinstance
                SET friendly_name = %s, instance_name = %s
                WHERE id = %s
            """, (new_name, new_uuid, active['id']))
            
            conn.commit()
            print(f"\n✅ Atualizado!")
        else:
            print("\n❌ Cancelado")
    
    except ValueError:
        print("❌ Entrada inválida!")
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    print("\n" + "="*80)
    print("🔧 FIX INSTÂNCIAS - RAILWAY REMOTE")
    print("="*80)
    
    # Pegar credenciais
    db_url = input("\nDigite a URL do PostgreSQL Railway: ").strip()
    
    if not db_url:
        print("❌ URL é obrigatória!")
        return
    
    # Conectar
    conn = connect_database(db_url)
    if not conn:
        return
    
    # Analisar
    instances, tenants = analyze_instances(conn)
    
    # Pegar Evolution API info
    print("\n" + "="*80)
    evo_url = input("\nURL Evolution (ENTER = https://evo.rbtec.com.br): ").strip()
    if not evo_url:
        evo_url = "https://evo.rbtec.com.br"
    
    evo_key = input("API Key Evolution: ").strip()
    
    if not evo_key:
        print("❌ API Key obrigatória!")
        conn.close()
        return
    
    # Buscar instâncias Evolution
    evolution_instances = list_evolution_instances(evo_url, evo_key)
    
    # Menu
    while True:
        print("\n" + "="*80)
        print("AÇÕES:")
        print("="*80)
        print("1. Limpar instâncias inativas")
        print("2. Atualizar instância ativa")
        print("3. Ver análise novamente")
        print("4. Sair")
        print("="*80)
        
        choice = input("\n❓ Opção: ").strip()
        
        if choice == '1':
            clean_inactive_instances(conn)
        elif choice == '2':
            update_active_instance(conn, evolution_instances)
        elif choice == '3':
            analyze_instances(conn)
        elif choice == '4':
            print("\n👋 Tchau!")
            break
        else:
            print("❌ Inválido!")
    
    conn.close()

if __name__ == '__main__':
    main()

