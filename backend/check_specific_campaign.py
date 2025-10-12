"""Verifica campanha específica"""
import os, sys, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign, CampaignContact, CampaignLog

campaign_id = '852a21e6-5290-4efb-b140-5e09e8f49f39'  # teste 001

print("\n" + "="*80)
print("🔍 VERIFICANDO CAMPANHA: teste 001")
print("="*80)

campaign = Campaign.objects.get(id=campaign_id)

print(f"\n📋 DADOS:")
print(f"   Nome: {campaign.name}")
print(f"   Status: {campaign.status}")
print(f"   Total contatos: {campaign.total_contacts}")
print(f"   Mensagens enviadas: {campaign.messages_sent}")

print(f"\n👥 CONTATOS:")
cc_list = CampaignContact.objects.filter(campaign=campaign)
print(f"   Total: {cc_list.count()}")
for cc in cc_list:
    print(f"   • {cc.contact.name} ({cc.contact.phone})")
    print(f"     Status: {cc.status}")
    if cc.error_message:
        print(f"     Erro: {cc.error_message}")

print(f"\n📝 LOGS:")
logs = CampaignLog.objects.filter(campaign=campaign).order_by('created_at')
print(f"   Total: {logs.count()}")
for log in logs:
    print(f"   [{log.log_type}] {log.message}")
    if log.details:
        print(f"      {log.details}")

print("\n" + "="*80)




