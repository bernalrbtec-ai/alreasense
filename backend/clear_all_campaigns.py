#!/usr/bin/env python
"""
Script para limpar TODAS as campanhas do sistema
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign, CampaignContact, CampaignLog
from apps.tenancy.models import Tenant

def clear_all_campaigns():
    """Limpa todas as campanhas do sistema"""
    try:
        print("🧹 LIMPANDO TODAS AS CAMPANHAS...")
        
        # Contar antes de deletar
        total_campaigns = Campaign.objects.count()
        total_contacts = CampaignContact.objects.count()
        total_logs = CampaignLog.objects.count()
        
        print(f"📊 ANTES DA LIMPEZA:")
        print(f"   Campanhas: {total_campaigns}")
        print(f"   Contatos: {total_contacts}")
        print(f"   Logs: {total_logs}")
        
        # Deletar em ordem (dependências primeiro)
        print("\n🗑️ Deletando logs de campanha...")
        CampaignLog.objects.all().delete()
        
        print("🗑️ Deletando contatos de campanha...")
        CampaignContact.objects.all().delete()
        
        print("🗑️ Deletando campanhas...")
        Campaign.objects.all().delete()
        
        # Verificar se foi limpo
        remaining_campaigns = Campaign.objects.count()
        remaining_contacts = CampaignContact.objects.count()
        remaining_logs = CampaignLog.objects.count()
        
        print(f"\n✅ APÓS A LIMPEZA:")
        print(f"   Campanhas restantes: {remaining_campaigns}")
        print(f"   Contatos restantes: {remaining_contacts}")
        print(f"   Logs restantes: {remaining_logs}")
        
        if remaining_campaigns == 0 and remaining_contacts == 0 and remaining_logs == 0:
            print("\n🎉 SUCESSO! Sistema completamente limpo!")
        else:
            print("\n⚠️ ATENÇÃO: Ainda restam dados!")
            
    except Exception as e:
        print(f"❌ ERRO durante limpeza: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🧹 LIMPEZA COMPLETA DO SISTEMA DE CAMPANHAS")
    print("=" * 60)
    
    # Confirmação
    confirm = input("\n⚠️ ATENÇÃO: Isso vai deletar TODAS as campanhas!\nDeseja continuar? (sim/não): ").lower()
    
    if confirm in ['sim', 's', 'yes', 'y']:
        success = clear_all_campaigns()
        if success:
            print("\n✅ Limpeza concluída com sucesso!")
        else:
            print("\n❌ Erro durante a limpeza!")
    else:
        print("\n❌ Operação cancelada pelo usuário.")
