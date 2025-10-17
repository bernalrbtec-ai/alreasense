"""
Script para DELETAR PERMANENTEMENTE todas as campanhas do cliente RBTEC
Usuário: paulo.bernal@rbtec.com.br
"""
import os
import django
import sys

# Configurar Django
sys.path.append('backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog, CampaignMessage
from apps.tenancy.models import Tenant

User = get_user_model()

def delete_rbtec_campaigns():
    """Deleta PERMANENTEMENTE todas as campanhas do cliente RBTEC"""
    
    try:
        # Buscar usuário
        user = User.objects.get(email='paulo.bernal@rbtec.com.br')
        print(f"✅ Usuário encontrado: {user.email}")
        
        # Buscar tenant
        tenant = user.tenant
        print(f"✅ Tenant encontrado: {tenant.name}")
        
        # Buscar todas as campanhas do tenant
        campaigns = Campaign.objects.filter(tenant=tenant)
        print(f"\n📊 Total de campanhas encontradas: {campaigns.count()}")
        
        if campaigns.count() == 0:
            print("ℹ️ Nenhuma campanha encontrada para deletar.")
            return
        
        # Mostrar campanhas
        print("\n📋 Campanhas que serão DELETADAS PERMANENTEMENTE:")
        for campaign in campaigns:
            print(f"  - {campaign.name} (Status: {campaign.status})")
            print(f"    Contatos: {campaign.total_contacts}")
        
        # Confirmar
        print("\n" + "="*60)
        print("⚠️  ATENÇÃO: Esta operação é IRREVERSÍVEL!")
        print("⚠️  Todas as campanhas, contatos e logs serão APAGADOS!")
        print("="*60)
        confirm = input("\n🗑️  Digite 'DELETAR' para confirmar a deleção permanente: ")
        
        if confirm.upper() != 'DELETAR':
            print("❌ Operação cancelada pelo usuário.")
            return
        
        print("\n🗑️  Deletando campanhas...")
        
        deleted_count = 0
        contacts_deleted = 0
        messages_deleted = 0
        logs_deleted = 0
        
        # Deletar cada campanha
        for campaign in campaigns:
            print(f"\n🗑️  Deletando: {campaign.name}")
            
            # Contar o que será deletado
            contacts_count = CampaignContact.objects.filter(campaign=campaign).count()
            messages_count = CampaignMessage.objects.filter(campaign=campaign).count()
            logs_count = CampaignLog.objects.filter(campaign=campaign).count()
            
            # Deletar contatos da campanha
            if contacts_count > 0:
                CampaignContact.objects.filter(campaign=campaign).delete()
                print(f"  ✅ {contacts_count} contatos deletados")
                contacts_deleted += contacts_count
            
            # Deletar mensagens da campanha
            if messages_count > 0:
                CampaignMessage.objects.filter(campaign=campaign).delete()
                print(f"  ✅ {messages_count} mensagens deletadas")
                messages_deleted += messages_count
            
            # Deletar logs da campanha
            if logs_count > 0:
                CampaignLog.objects.filter(campaign=campaign).delete()
                print(f"  ✅ {logs_count} logs deletados")
                logs_deleted += logs_count
            
            # Deletar a campanha
            campaign.delete()
            print(f"  ✅ Campanha '{campaign.name}' DELETADA")
            deleted_count += 1
        
        print("\n" + "="*60)
        print("✅ TODAS AS CAMPANHAS FORAM DELETADAS COM SUCESSO!")
        print("="*60)
        print("\nResumo:")
        print(f"  - Campanhas deletadas: {deleted_count}")
        print(f"  - Contatos deletados: {contacts_deleted}")
        print(f"  - Mensagens deletadas: {messages_deleted}")
        print(f"  - Logs deletados: {logs_deleted}")
        print(f"\n🗑️  Total de registros removidos: {deleted_count + contacts_deleted + messages_deleted + logs_deleted}")
        
    except User.DoesNotExist:
        print("❌ Usuário 'paulo.bernal@rbtec.com.br' não encontrado!")
    except Exception as e:
        print(f"❌ Erro ao deletar campanhas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("="*60)
    print("🗑️  SCRIPT DE DELEÇÃO DE CAMPANHAS - CLIENTE RBTEC")
    print("="*60)
    print("Usuário: paulo.bernal@rbtec.com.br")
    print("Ação: DELETAR PERMANENTEMENTE todas as campanhas")
    print("="*60)
    print()
    
    delete_rbtec_campaigns()

