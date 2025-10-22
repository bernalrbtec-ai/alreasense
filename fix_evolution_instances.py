"""
Script para limpar e atualizar instâncias Evolution.
Remove registros inativos antigos e atualiza com dados corretos da Evolution API.
"""
import os
import sys
import django
import requests
from pathlib import Path

# Setup Django
current_dir = Path(__file__).parent
backend_dir = current_dir / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant

def list_database_instances():
    """Lista instâncias no banco."""
    print("\n" + "="*80)
    print("📋 INSTÂNCIAS NO BANCO DE DADOS")
    print("="*80)
    
    instances = WhatsAppInstance.objects.all().order_by('created_at')
    
    for inst in instances:
        status_emoji = "✅" if inst.is_active else "❌"
        print(f"\n{status_emoji} ID: {inst.id}")
        print(f"   Nome amigável: {inst.friendly_name or '(vazio)'}")
        print(f"   Instance name (UUID): {inst.instance_name or '(vazio)'}")
        print(f"   Tenant: {inst.tenant.name if inst.tenant else 'Global'}")
        print(f"   Ativo: {inst.is_active}")
        print(f"   Status: {inst.status}")
    
    return instances

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
            print(f"❌ Erro ao buscar instâncias: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return []
        
        instances = response.json()
        
        print(f"\n✅ Encontradas {len(instances)} instâncias:\n")
        
        for idx, inst in enumerate(instances, 1):
            instance_data = inst.get('instance', {})
            instance_name = instance_data.get('instanceName', 'N/A')
            instance_id = instance_data.get('instanceId', 'N/A')
            status = instance_data.get('status', 'N/A')
            
            print(f"{idx}. Nome: {instance_name}")
            print(f"   UUID: {instance_id}")
            print(f"   Status: {status}\n")
        
        return instances
    
    except Exception as e:
        print(f"❌ Erro ao buscar da Evolution API: {e}")
        return []

def clean_inactive_instances():
    """Remove instâncias inativas antigas."""
    print("\n" + "="*80)
    print("🗑️  LIMPANDO INSTÂNCIAS INATIVAS")
    print("="*80)
    
    inactive = WhatsAppInstance.objects.filter(is_active=False)
    count = inactive.count()
    
    if count == 0:
        print("\n✅ Nenhuma instância inativa para deletar")
        return
    
    print(f"\n⚠️  Encontradas {count} instâncias inativas:")
    for inst in inactive:
        tenant_name = inst.tenant.name if inst.tenant else 'Global'
        print(f"   - ID {inst.id}: {inst.friendly_name or '(sem nome)'} - Tenant: {tenant_name}")
    
    confirm = input(f"\n❓ Deletar {count} instâncias inativas? (digite 'SIM'): ")
    
    if confirm == 'SIM':
        deleted = inactive.delete()[0]
        print(f"\n✅ {deleted} instâncias deletadas!")
    else:
        print("\n❌ Operação cancelada")

def update_active_instance(evolution_instances, tenant_name='RBTec Informática'):
    """Atualiza instância ativa com dados corretos."""
    print("\n" + "="*80)
    print("🔧 ATUALIZANDO INSTÂNCIA ATIVA")
    print("="*80)
    
    # Buscar tenant
    try:
        tenant = Tenant.objects.get(name=tenant_name)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{tenant_name}' não encontrado!")
        return
    
    # Buscar instância ativa
    active = WhatsAppInstance.objects.filter(
        tenant=tenant,
        is_active=True
    ).first()
    
    if not active:
        print(f"❌ Nenhuma instância ativa para tenant {tenant_name}")
        return
    
    print(f"\n📋 Instância ativa atual:")
    print(f"   ID: {active.id}")
    print(f"   Nome amigável: {active.friendly_name or '(vazio)'}")
    print(f"   Instance name (UUID): {active.instance_name or '(vazio)'}")
    
    if not evolution_instances:
        print("\n⚠️  Não há instâncias da Evolution API para usar")
        return
    
    # Mostrar opções
    print(f"\n📋 Escolha qual instância Evolution usar:")
    for idx, inst in enumerate(evolution_instances, 1):
        instance_data = inst.get('instance', {})
        instance_name = instance_data.get('instanceName', 'N/A')
        instance_id = instance_data.get('instanceId', 'N/A')
        status = instance_data.get('status', 'N/A')
        
        print(f"\n{idx}. Nome: {instance_name}")
        print(f"   UUID: {instance_id}")
        print(f"   Status: {status}")
    
    try:
        choice = int(input(f"\n❓ Digite o número (1-{len(evolution_instances)}): ")) - 1
        
        if choice < 0 or choice >= len(evolution_instances):
            print("❌ Escolha inválida!")
            return
        
        selected = evolution_instances[choice]
        instance_data = selected.get('instance', {})
        new_name = instance_data.get('instanceName')
        new_instance_name = instance_data.get('instanceId')
        
        print(f"\n✅ Selecionado:")
        print(f"   Nome: {new_name}")
        print(f"   UUID: {new_instance_name}")
        
        print(f"\n🔄 Mudanças:")
        print(f"   Nome amigável: '{active.friendly_name}' → '{new_name}'")
        print(f"   Instance name (UUID): '{active.instance_name}' → '{new_instance_name}'")
        
        confirm = input(f"\n❓ Confirmar atualização? (digite 'SIM'): ")
        
        if confirm == 'SIM':
            active.friendly_name = new_name
            active.instance_name = new_instance_name
            active.save()
            print(f"\n✅ Instância atualizada com sucesso!")
        else:
            print("\n❌ Operação cancelada")
    
    except ValueError:
        print("❌ Entrada inválida!")
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    print("\n" + "="*80)
    print("🔧 FIX - INSTÂNCIAS EVOLUTION")
    print("="*80)
    
    # Configurações
    EVOLUTION_URL = input("\nDigite a URL da Evolution (ou ENTER para https://evo.rbtec.com.br): ").strip()
    if not EVOLUTION_URL:
        EVOLUTION_URL = "https://evo.rbtec.com.br"
    
    EVOLUTION_API_KEY = input("Digite a API Key da Evolution: ").strip()
    
    if not EVOLUTION_API_KEY:
        print("❌ API Key é obrigatória!")
        return
    
    # 1. Listar o que tem no banco
    list_database_instances()
    
    # 2. Listar o que tem na Evolution API
    evolution_instances = list_evolution_instances(EVOLUTION_URL, EVOLUTION_API_KEY)
    
    # 3. Menu de ações
    while True:
        print("\n" + "="*80)
        print("AÇÕES DISPONÍVEIS:")
        print("="*80)
        print("1. Limpar instâncias inativas (lixo)")
        print("2. Atualizar instância ativa com dados corretos")
        print("3. Ver instâncias no banco novamente")
        print("4. Sair")
        print("="*80)
        
        choice = input("\n❓ Escolha uma opção: ").strip()
        
        if choice == '1':
            clean_inactive_instances()
        elif choice == '2':
            update_active_instance(evolution_instances)
        elif choice == '3':
            list_database_instances()
        elif choice == '4':
            print("\n👋 Tchau!")
            break
        else:
            print("❌ Opção inválida!")

if __name__ == '__main__':
    main()

