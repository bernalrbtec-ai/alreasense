#!/usr/bin/env python
"""
Script Python para zerar todas as campanhas de um tenant

Uso:
    python scripts/zerar_campanhas_tenant.py "RBTec Informática"
    
Ou execute diretamente e informe o nome do tenant quando solicitado.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from apps.tenancy.models import Tenant
from apps.campaigns.models import (
    Campaign,
    CampaignMessage,
    CampaignContact,
    CampaignLog,
    CampaignNotification
)


def zerar_campanhas_tenant(tenant_name: str, confirmar: bool = False):
    """
    Zera todas as campanhas de um tenant
    
    Args:
        tenant_name: Nome do tenant (pode ser parcial, case-insensitive)
        confirmar: Se True, executa a exclusão. Se False, apenas mostra o que será deletado.
    """
    try:
        # Buscar tenant
        tenant = Tenant.objects.filter(name__icontains=tenant_name).first()
        
        if not tenant:
            print(f"❌ Tenant '{tenant_name}' não encontrado!")
            print("\nTenants disponíveis:")
            for t in Tenant.objects.all():
                print(f"  - {t.name} (ID: {t.id})")
            return False
        
        print(f"✅ Tenant encontrado: {tenant.name} (ID: {tenant.id})")
        
        # Contar registros que serão deletados
        campaigns = Campaign.objects.filter(tenant=tenant)
        campaign_count = campaigns.count()
        
        campaign_messages = CampaignMessage.objects.filter(campaign__tenant=tenant)
        campaign_contacts = CampaignContact.objects.filter(campaign__tenant=tenant)
        campaign_logs = CampaignLog.objects.filter(campaign__tenant=tenant)
        campaign_notifications = CampaignNotification.objects.filter(tenant=tenant)
        
        print("\n" + "="*60)
        print("📊 RESUMO DO QUE SERÁ DELETADO:")
        print("="*60)
        print(f"  Campanhas: {campaign_count}")
        print(f"  Mensagens de Campanha: {campaign_messages.count()}")
        print(f"  Contatos de Campanha: {campaign_contacts.count()}")
        print(f"  Logs de Campanha: {campaign_logs.count()}")
        print(f"  Notificações de Campanha: {campaign_notifications.count()}")
        print("="*60)
        
        if campaign_count == 0:
            print("\n✅ Nenhuma campanha encontrada para este tenant. Nada a fazer.")
            return True
        
        if not confirmar:
            print("\n⚠️  MODO DE VISUALIZAÇÃO - Nada foi deletado ainda!")
            print("   Para executar a exclusão, chame a função com confirmar=True")
            print("   Ou execute: python scripts/zerar_campanhas_tenant.py \"Nome do Tenant\" --confirmar")
            return False
        
        # Executar exclusão em transação
        with transaction.atomic():
            print("\n🗑️  Iniciando exclusão...")
            
            # 1. Deletar notificações
            notifications_deleted = campaign_notifications.count()
            campaign_notifications.delete()
            print(f"  ✅ {notifications_deleted} notificações deletadas")
            
            # 2. Deletar logs
            logs_deleted = campaign_logs.count()
            campaign_logs.delete()
            print(f"  ✅ {logs_deleted} logs deletados")
            
            # 3. Deletar contatos de campanha
            contacts_deleted = campaign_contacts.count()
            campaign_contacts.delete()
            print(f"  ✅ {contacts_deleted} contatos de campanha deletados")
            
            # 4. Deletar mensagens de campanha
            messages_deleted = campaign_messages.count()
            campaign_messages.delete()
            print(f"  ✅ {messages_deleted} mensagens deletadas")
            
            # 5. Deletar relacionamentos ManyToMany (instances)
            for campaign in campaigns:
                campaign.instances.clear()
            
            # 6. Deletar campanhas
            campaigns_deleted = campaign_count
            campaigns.delete()
            print(f"  ✅ {campaigns_deleted} campanhas deletadas")
        
        print("\n" + "="*60)
        print("✅ EXCLUSÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        
        # Verificação final
        remaining = Campaign.objects.filter(tenant=tenant).count()
        if remaining == 0:
            print("✅ Verificação: Nenhuma campanha restante para este tenant.")
        else:
            print(f"⚠️  ATENÇÃO: Ainda restam {remaining} campanhas!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO ao zerar campanhas: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Zerar todas as campanhas de um tenant')
    parser.add_argument('tenant_name', nargs='?', help='Nome do tenant (pode ser parcial)')
    parser.add_argument('--confirmar', action='store_true', help='Confirmar exclusão (sem isso, apenas mostra o que será deletado)')
    
    args = parser.parse_args()
    
    if not args.tenant_name:
        print("Digite o nome do tenant:")
        tenant_name = input("> ").strip()
    else:
        tenant_name = args.tenant_name
    
    if not tenant_name:
        print("❌ Nome do tenant não fornecido!")
        sys.exit(1)
    
    zerar_campanhas_tenant(tenant_name, confirmar=args.confirmar)

