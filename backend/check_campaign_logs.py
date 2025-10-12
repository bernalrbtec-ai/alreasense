"""
Script para verificar logs de campanha
"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign, CampaignContact, CampaignLog

def check_last_campaign():
    print("\n" + "="*80)
    print("🔍 VERIFICANDO ÚLTIMA CAMPANHA")
    print("="*80)
    
    campaign = Campaign.objects.last()
    if not campaign:
        print("❌ Nenhuma campanha encontrada")
        return
    
    print(f"\n📋 CAMPANHA: {campaign.name}")
    print(f"   ID: {campaign.id}")
    print(f"   Status: {campaign.status}")
    print(f"   Modo de rotação: {campaign.rotation_mode}")
    print(f"   Criada em: {campaign.created_at}")
    print(f"   Iniciada em: {campaign.started_at}")
    print(f"   Concluída em: {campaign.completed_at}")
    
    print(f"\n📊 ESTATÍSTICAS:")
    print(f"   Total de contatos: {campaign.total_contacts}")
    print(f"   Mensagens enviadas: {campaign.messages_sent}")
    print(f"   Mensagens entregues: {campaign.messages_delivered}")
    print(f"   Mensagens lidas: {campaign.messages_read}")
    print(f"   Mensagens com falha: {campaign.messages_failed}")
    
    print(f"\n⚡ INSTÂNCIAS SELECIONADAS:")
    for instance in campaign.instances.all():
        print(f"   • {instance.friendly_name} ({instance.phone_number})")
        print(f"     Status: {instance.connection_state}")
        print(f"     Health: {instance.health_score}")
    
    print(f"\n💬 MENSAGENS:")
    for msg in campaign.messages.all():
        print(f"   {msg.order}. {msg.content[:50]}...")
        print(f"      Usada: {msg.times_used}x")
    
    print(f"\n👥 CONTATOS DA CAMPANHA:")
    contacts = CampaignContact.objects.filter(campaign=campaign)
    print(f"   Total: {contacts.count()}")
    
    for cc in contacts[:10]:
        print(f"   • {cc.contact.name} ({cc.contact.phone})")
        print(f"     Status: {cc.status}")
        if cc.error_message:
            print(f"     Erro: {cc.error_message}")
        if cc.sent_at:
            print(f"     Enviado em: {cc.sent_at}")
    
    print(f"\n📝 LOGS (últimos 20):")
    logs = CampaignLog.objects.filter(campaign=campaign).order_by('-created_at')[:20]
    print(f"   Total de logs: {CampaignLog.objects.filter(campaign=campaign).count()}")
    
    if logs.count() == 0:
        print("   ⚠️ Nenhum log encontrado!")
    else:
        for log in logs:
            severity_icon = {
                'info': '📘',
                'warning': '⚠️',
                'error': '❌',
                'critical': '🔴'
            }.get(log.severity, '📄')
            
            print(f"   {severity_icon} [{log.log_type}] {log.message}")
            if log.details:
                print(f"      Detalhes: {log.details}")
    
    print("\n" + "="*80)
    print("✅ VERIFICAÇÃO COMPLETA")
    print("="*80 + "\n")

if __name__ == '__main__':
    check_last_campaign()




