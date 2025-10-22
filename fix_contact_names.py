"""
Script para corrigir nomes de contatos nas conversas.
Busca o nome correto via Evolution API e atualiza o banco.
"""
import os
import sys
import django
import asyncio
import httpx
from pathlib import Path

# Setup Django
current_dir = Path(__file__).parent
backend_dir = current_dir / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.chat.models import Conversation
from apps.connections.models import EvolutionConnection
from apps.tenancy.models import Tenant


async def fetch_contact_name(instance: EvolutionConnection, phone: str) -> str | None:
    """Busca o nome do contato via Evolution API."""
    base_url = instance.base_url.rstrip('/')
    headers = {
        'apikey': instance.api_key,
        'Content-Type': 'application/json'
    }
    
    clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
    endpoint = f"{base_url}/chat/whatsappNumbers/{instance.name}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                endpoint,
                json={'numbers': [clean_phone]},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    contact_info = data[0]
                    return contact_info.get('name') or contact_info.get('pushname', '')
    except Exception as e:
        print(f"   ❌ Erro ao buscar nome: {e}")
    
    return None


async def fix_contact_names(tenant_id=None, dry_run=False):
    """
    Corrige nomes de contatos nas conversas.
    
    Args:
        tenant_id: Se fornecido, corrige apenas esse tenant
        dry_run: Se True, apenas mostra o que seria corrigido
    """
    
    print("\n" + "="*80)
    print("🔧 CORREÇÃO DE NOMES DE CONTATOS")
    print("="*80)
    
    if dry_run:
        print("\n🔍 MODO DRY-RUN - Apenas visualização, nada será alterado")
    
    # Filtrar tenants
    if tenant_id:
        tenants = Tenant.objects.filter(id=tenant_id)
    else:
        tenants = Tenant.objects.all()
    
    for tenant in tenants:
        print(f"\n{'='*80}")
        print(f"📋 TENANT: {tenant.name}")
        print(f"{'='*80}")
        
        # Buscar instância ativa
        instance = EvolutionConnection.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()
        
        if not instance:
            print("❌ Nenhuma instância Evolution ativa")
            continue
        
        print(f"✅ Instância: {instance.name}")
        
        # Buscar conversas individuais
        conversations = Conversation.objects.filter(
            tenant=tenant,
            conversation_type='individual'
        ).order_by('-last_message_at')
        
        total = conversations.count()
        print(f"📊 Total de conversas individuais: {total}\n")
        
        if total == 0:
            print("✅ Nenhuma conversa para corrigir")
            continue
        
        updated = 0
        skipped = 0
        errors = 0
        
        for idx, conv in enumerate(conversations, 1):
            phone = conv.contact_phone
            current_name = conv.contact_name
            
            print(f"[{idx}/{total}] 📞 {phone}")
            print(f"         Nome atual: '{current_name}'")
            
            # Buscar nome correto
            correct_name = await fetch_contact_name(instance, phone)
            
            if correct_name:
                if correct_name != current_name:
                    print(f"         ✅ Nome correto: '{correct_name}'")
                    
                    if not dry_run:
                        conv.contact_name = correct_name
                        conv.save(update_fields=['contact_name'])
                        print(f"         💾 Atualizado!")
                    else:
                        print(f"         🔍 [DRY-RUN] Seria atualizado")
                    
                    updated += 1
                else:
                    print(f"         ⏭️ Nome já está correto")
                    skipped += 1
            else:
                print(f"         ⚠️ Nome não encontrado na API")
                errors += 1
            
            print()
            
            # Delay para não sobrecarregar API
            await asyncio.sleep(0.3)
        
        # Resumo
        print("="*80)
        print(f"📊 RESUMO - {tenant.name}:")
        print(f"   ✅ Atualizados: {updated}")
        print(f"   ⏭️ Já corretos: {skipped}")
        print(f"   ⚠️ Erros/não encontrados: {errors}")
        print("="*80)
    
    print("\n" + "="*80)
    if dry_run:
        print("✅ DRY-RUN CONCLUÍDO - Nenhum dado foi alterado")
    else:
        print("✅ CORREÇÃO CONCLUÍDA!")
    print("="*80 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Corrige nomes de contatos nas conversas'
    )
    parser.add_argument(
        '--tenant-id',
        type=str,
        help='ID do tenant para corrigir (UUID)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra o que seria corrigido, sem alterar'
    )
    
    args = parser.parse_args()
    
    # Executar
    asyncio.run(fix_contact_names(
        tenant_id=args.tenant_id,
        dry_run=args.dry_run
    ))


if __name__ == '__main__':
    main()

