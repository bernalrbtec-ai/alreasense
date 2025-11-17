#!/usr/bin/env python
"""
Script para limpar todos os contatos de um tenant específico.

Uso:
    python scripts/limpar_contatos_tenant.py --tenant-name "RBTec"
    python scripts/limpar_contatos_tenant.py --tenant-id "uuid-do-tenant"
"""

import os
import sys
import django
import argparse

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import transaction
from apps.contacts.models import Contact, ContactImport
from apps.campaigns.models import CampaignContact, CampaignNotification
from apps.tenancy.models import Tenant


def limpar_contatos_tenant(tenant_name=None, tenant_id=None, dry_run=True):
    """
    Limpa todos os contatos de um tenant.
    
    Args:
        tenant_name: Nome do tenant (busca case-insensitive)
        tenant_id: UUID do tenant
        dry_run: Se True, apenas mostra o que seria deletado sem deletar
    """
    # Buscar tenant
    if tenant_id:
        tenant = Tenant.objects.filter(id=tenant_id).first()
    elif tenant_name:
        tenant = Tenant.objects.filter(name__icontains=tenant_name).first()
    else:
        print("❌ Erro: Forneça --tenant-name ou --tenant-id")
        return False
    
    if not tenant:
        print(f"❌ Tenant não encontrado!")
        if tenant_name:
            print(f"   Buscado por nome: {tenant_name}")
        if tenant_id:
            print(f"   Buscado por ID: {tenant_id}")
        return False
    
    print(f"\n{'='*80}")
    print(f"🗑️  LIMPEZA DE CONTATOS - TENANT: {tenant.name}")
    print(f"{'='*80}")
    print(f"Tenant ID: {tenant.id}")
    print(f"Modo: {'DRY RUN (simulação)' if dry_run else 'EXECUÇÃO REAL'}")
    print(f"{'='*80}\n")
    
    # Contar contatos
    contacts_count = Contact.objects.filter(tenant=tenant).count()
    campaign_contacts_count = CampaignContact.objects.filter(contact__tenant=tenant).count()
    campaign_notifications_count = CampaignNotification.objects.filter(contact__tenant=tenant).count()
    imports_count = ContactImport.objects.filter(tenant=tenant).count()
    
    print(f"📊 ESTATÍSTICAS:")
    print(f"   Contatos: {contacts_count}")
    print(f"   CampaignContact: {campaign_contacts_count}")
    print(f"   CampaignNotification: {campaign_notifications_count}")
    print(f"   Importações (histórico): {imports_count}")
    print()
    
    if contacts_count == 0:
        print("✅ Nenhum contato encontrado. Nada a fazer.")
        return True
    
    if dry_run:
        print("⚠️  MODO DRY RUN - Nada será deletado.")
        print("   Execute com --execute para deletar de verdade.\n")
        return True
    
    # Confirmar
    print("⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!")
    resposta = input("   Digite 'SIM' para confirmar: ")
    
    if resposta != 'SIM':
        print("❌ Operação cancelada.")
        return False
    
    # Deletar
    try:
        with transaction.atomic():
            print("\n🗑️  Deletando...")
            
            # 1. Deletar CampaignNotification (mais específico primeiro)
            deleted_notifications = CampaignNotification.objects.filter(
                contact__tenant=tenant
            ).delete()
            print(f"   ✅ CampaignNotification: {deleted_notifications[0]} deletados")
            
            # 2. Deletar CampaignContact
            deleted_campaign_contacts = CampaignContact.objects.filter(
                contact__tenant=tenant
            ).delete()
            print(f"   ✅ CampaignContact: {deleted_campaign_contacts[0]} deletados")
            
            # 3. Deletar ContactImport (histórico)
            deleted_imports = ContactImport.objects.filter(tenant=tenant).delete()
            print(f"   ✅ ContactImport: {deleted_imports[0]} deletados")
            
            # 4. Deletar Contact (vai deletar automaticamente tags e lists M2M)
            deleted_contacts = Contact.objects.filter(tenant=tenant).delete()
            print(f"   ✅ Contact: {deleted_contacts[0]} deletados")
            
            print(f"\n✅ Limpeza concluída com sucesso!")
            print(f"   Total de contatos deletados: {deleted_contacts[0]}")
            
        return True
        
    except Exception as e:
        print(f"\n❌ Erro ao deletar: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Limpa todos os contatos de um tenant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Simulação (dry run)
  python scripts/limpar_contatos_tenant.py --tenant-name "RBTec"
  
  # Execução real
  python scripts/limpar_contatos_tenant.py --tenant-name "RBTec" --execute
  
  # Usando tenant_id
  python scripts/limpar_contatos_tenant.py --tenant-id "uuid-aqui" --execute
        """
    )
    
    parser.add_argument(
        '--tenant-name',
        type=str,
        help='Nome do tenant (busca case-insensitive)'
    )
    
    parser.add_argument(
        '--tenant-id',
        type=str,
        help='UUID do tenant'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Executa a deleção (sem isso, apenas simula)'
    )
    
    args = parser.parse_args()
    
    if not args.tenant_name and not args.tenant_id:
        parser.print_help()
        return
    
    limpar_contatos_tenant(
        tenant_name=args.tenant_name,
        tenant_id=args.tenant_id,
        dry_run=not args.execute
    )


if __name__ == '__main__':
    main()

