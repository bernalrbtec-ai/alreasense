"""
Script para zerar todas as campanhas do cliente RBTEC
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
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
from apps.tenancy.models import Tenant

User = get_user_model()

def reset_rbtec_campaigns():
    """Zera todas as campanhas do cliente RBTEC"""
    
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
            print("ℹ️ Nenhuma campanha encontrada para zerar.")
            return
        
        # Mostrar campanhas
        print("\n📋 Campanhas a serem zeradas:")
        for campaign in campaigns:
            print(f"  - {campaign.name} (Status: {campaign.status})")
            print(f"    Enviadas: {campaign.messages_sent}, Entregues: {campaign.messages_delivered}")
            print(f"    Lidas: {campaign.messages_read}, Falhas: {campaign.messages_failed}")
        
        # Confirmar
        confirm = input("\n⚠️ Deseja ZERAR todas essas campanhas? (digite 'SIM' para confirmar): ")
        
        if confirm.upper() != 'SIM':
            print("❌ Operação cancelada pelo usuário.")
            return
        
        print("\n🔄 Zerando campanhas...")
        
        # Zerar cada campanha
        for campaign in campaigns:
            print(f"\n🔧 Processando: {campaign.name}")
            
            # 1. Zerar contadores da campanha
            campaign.messages_sent = 0
            campaign.messages_delivered = 0
            campaign.messages_read = 0
            campaign.messages_failed = 0
            # progress_percentage, success_rate e read_rate são calculados automaticamente
            campaign.last_message_sent_at = None
            campaign.next_message_scheduled_at = None
            campaign.next_contact_name = None
            campaign.next_contact_phone = None
            campaign.next_instance_name = None
            campaign.last_contact_name = None
            campaign.last_contact_phone = None
            campaign.last_instance_name = None
            campaign.started_at = None
            campaign.completed_at = None
            
            # 2. Resetar status para draft
            campaign.status = 'draft'
            
            campaign.save()
            print(f"  ✅ Contadores zerados")
            
            # 3. Resetar todos os contatos da campanha para 'pending'
            contacts = CampaignContact.objects.filter(campaign=campaign)
            contacts_count = contacts.count()
            
            if contacts_count > 0:
                contacts.update(
                    status='pending',
                    sent_at=None,
                    delivered_at=None,
                    read_at=None,
                    whatsapp_message_id=None,
                    error_message=None
                )
                print(f"  ✅ {contacts_count} contatos resetados para 'pending'")
            
            # 4. Limpar logs da campanha (opcional - comentado para manter histórico)
            # logs = CampaignLog.objects.filter(campaign=campaign)
            # logs_count = logs.count()
            # if logs_count > 0:
            #     logs.delete()
            #     print(f"  ✅ {logs_count} logs removidos")
            
            print(f"  ✨ Campanha '{campaign.name}' zerada com sucesso!")
        
        print("\n" + "="*60)
        print("✅ TODAS AS CAMPANHAS FORAM ZERADAS COM SUCESSO!")
        print("="*60)
        print("\nResumo:")
        print(f"  - Total de campanhas zeradas: {campaigns.count()}")
        print(f"  - Status: Todas em 'draft'")
        print(f"  - Contadores: Todos zerados")
        print(f"  - Contatos: Todos em 'pending'")
        print(f"  - Logs: Mantidos para histórico")
        
    except User.DoesNotExist:
        print("❌ Usuário 'paulo.bernal@rbtec.com.br' não encontrado!")
    except Exception as e:
        print(f"❌ Erro ao zerar campanhas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("="*60)
    print("🔧 SCRIPT DE RESET DE CAMPANHAS - CLIENTE RBTEC")
    print("="*60)
    print("Usuário: paulo.bernal@rbtec.com.br")
    print("Ação: Zerar todas as campanhas")
    print("="*60)
    print()
    
    reset_rbtec_campaigns()

