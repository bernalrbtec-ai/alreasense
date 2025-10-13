#!/usr/bin/env python
"""
Script para limpar todas as campanhas da RBTec
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.tenancy.models import Tenant
from apps.campaigns.models import Campaign, CampaignContact, CampaignLog

def clear_rbtec_campaigns():
    """Limpa todas as campanhas da RBTec"""
    
    print("🧹 Limpando campanhas da RBTec...")
    
    try:
        # Encontrar tenant da RBTec
        rbtec_tenant = Tenant.objects.filter(name__icontains='rbtec').first()
        
        if not rbtec_tenant:
            print("❌ Tenant RBTec não encontrado!")
            return
        
        print(f"✅ Tenant encontrado: {rbtec_tenant.name}")
        
        # Contar campanhas antes
        campaigns_count = Campaign.objects.filter(tenant=rbtec_tenant).count()
        contacts_count = CampaignContact.objects.filter(campaign__tenant=rbtec_tenant).count()
        logs_count = CampaignLog.objects.filter(campaign__tenant=rbtec_tenant).count()
        
        print(f"📊 Antes da limpeza:")
        print(f"   Campanhas: {campaigns_count}")
        print(f"   Contatos de campanha: {contacts_count}")
        print(f"   Logs de campanha: {logs_count}")
        
        if campaigns_count == 0:
            print("✅ Nenhuma campanha encontrada para limpar!")
            return
        
        # Confirmar limpeza
        confirm = input(f"\n⚠️  Tem certeza que quer deletar {campaigns_count} campanhas? (digite 'SIM' para confirmar): ")
        
        if confirm != 'SIM':
            print("❌ Limpeza cancelada!")
            return
        
        # Deletar logs primeiro (foreign key)
        deleted_logs = CampaignLog.objects.filter(campaign__tenant=rbtec_tenant).delete()
        print(f"🗑️  Deletados {deleted_logs[0]} logs de campanha")
        
        # Deletar contatos de campanha
        deleted_contacts = CampaignContact.objects.filter(campaign__tenant=rbtec_tenant).delete()
        print(f"🗑️  Deletados {deleted_contacts[0]} contatos de campanha")
        
        # Deletar campanhas
        deleted_campaigns = Campaign.objects.filter(tenant=rbtec_tenant).delete()
        print(f"🗑️  Deletadas {deleted_campaigns[0]} campanhas")
        
        print("✅ Limpeza concluída com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante a limpeza: {str(e)}")

if __name__ == "__main__":
    clear_rbtec_campaigns()
