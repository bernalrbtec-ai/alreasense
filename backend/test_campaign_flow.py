"""
Script para testar fluxo completo de campanhas
"""
import os
import sys
import django
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign, CampaignContact, CampaignLog, CampaignMessage
from apps.notifications.models import WhatsAppInstance
from apps.contacts.models import Contact, Tag
from apps.tenancy.models import Tenant
from apps.authn.models import User

def test_campaign_flow():
    print("\n" + "="*80)
    print("🧪 TESTE COMPLETO DO FLUXO DE CAMPANHAS")
    print("="*80)
    
    # 1. Buscar dados necessários
    print("\n1️⃣ PREPARANDO AMBIENTE...")
    
    tenant = Tenant.objects.first()
    if not tenant:
        print("❌ Nenhum tenant encontrado")
        return
    print(f"✅ Tenant: {tenant.name}")
    
    user = User.objects.filter(tenant=tenant, role='admin').first()
    if not user:
        print("❌ Nenhum usuário admin encontrado")
        return
    print(f"✅ Usuário: {user.email}")
    
    instance = WhatsAppInstance.objects.filter(tenant=tenant).first()
    if not instance:
        print("❌ Nenhuma instância encontrada")
        return
    print(f"✅ Instância: {instance.friendly_name} (Health: {instance.health_score})")
    
    tag = Tag.objects.filter(tenant=tenant).first()
    if not tag:
        print("❌ Nenhuma tag encontrada")
        return
    
    contacts = Contact.objects.filter(
        tenant=tenant,
        tags=tag,
        is_active=True,
        opted_out=False
    )[:5]  # Pegar apenas 5 contatos para teste
    
    if contacts.count() == 0:
        print("❌ Nenhum contato com esta tag")
        return
    
    print(f"✅ Tag: {tag.name} ({contacts.count()} contatos)")
    
    # 2. Criar campanha
    print("\n2️⃣ CRIANDO CAMPANHA...")
    
    campaign = Campaign.objects.create(
        tenant=tenant,
        created_by=user,
        name="Teste Automático",
        description="Campanha criada automaticamente para teste",
        rotation_mode='intelligent',
        status='draft'
    )
    
    # Adicionar instância
    campaign.instances.add(instance)
    
    # Criar mensagem
    msg = CampaignMessage.objects.create(
        campaign=campaign,
        content="🧪 Esta é uma mensagem de teste automático do sistema.",
        order=1
    )
    
    print(f"✅ Campanha criada: {campaign.name} (ID: {campaign.id})")
    print(f"   Status: {campaign.status}")
    
    # 3. Adicionar contatos
    print("\n3️⃣ ADICIONANDO CONTATOS...")
    
    campaign_contacts = []
    for contact in contacts:
        campaign_contacts.append(
            CampaignContact(
                campaign=campaign,
                contact=contact,
                status='pending'
            )
        )
    
    CampaignContact.objects.bulk_create(campaign_contacts)
    campaign.total_contacts = len(campaign_contacts)
    campaign.save()
    
    print(f"✅ {campaign.total_contacts} contatos adicionados")
    for cc in CampaignContact.objects.filter(campaign=campaign)[:3]:
        print(f"   • {cc.contact.name} ({cc.contact.phone})")
    
    # 4. Iniciar campanha
    print("\n4️⃣ INICIANDO CAMPANHA...")
    
    campaign.start()
    CampaignLog.log_campaign_started(campaign, user)
    print(f"✅ Campanha iniciada - Status: {campaign.status}")
    
    # Disparar task
    from apps.campaigns.tasks import process_campaign
    task = process_campaign.delay(str(campaign.id))
    print(f"✅ Task Celery disparada: {task.id}")
    
    # 5. Aguardar processamento
    print("\n5️⃣ AGUARDANDO PROCESSAMENTO...")
    print("⏳ Aguardando 3 segundos...")
    time.sleep(3)
    
    # Verificar progresso
    campaign.refresh_from_db()
    print(f"📊 Progresso:")
    print(f"   Status: {campaign.status}")
    print(f"   Enviadas: {campaign.messages_sent}/{campaign.total_contacts}")
    print(f"   Entregues: {campaign.messages_delivered}")
    print(f"   Falhas: {campaign.messages_failed}")
    
    # Verificar contatos
    pending = CampaignContact.objects.filter(campaign=campaign, status='pending').count()
    sent = CampaignContact.objects.filter(campaign=campaign, status='sent').count()
    failed = CampaignContact.objects.filter(campaign=campaign, status='failed').count()
    
    print(f"\n📋 Status dos Contatos:")
    print(f"   Pendentes: {pending}")
    print(f"   Enviados: {sent}")
    print(f"   Falhas: {failed}")
    
    # 6. Testar PAUSAR
    if campaign.status == 'running':
        print("\n6️⃣ TESTANDO PAUSAR...")
        campaign.pause()
        print(f"✅ Campanha pausada - Status: {campaign.status}")
        print("⏳ Aguardando 2 segundos...")
        time.sleep(2)
        
        # Verificar se task realmente parou
        campaign.refresh_from_db()
        msgs_antes = campaign.messages_sent
        print(f"   Mensagens antes da pausa: {msgs_antes}")
        time.sleep(3)
        campaign.refresh_from_db()
        msgs_depois = campaign.messages_sent
        print(f"   Mensagens após pausa: {msgs_depois}")
        
        if msgs_antes == msgs_depois:
            print("✅ PAUSA FUNCIONOU - Não enviou mais mensagens")
        else:
            print("❌ PAUSA FALHOU - Continuou enviando")
        
        # 7. Testar RETOMAR
        print("\n7️⃣ TESTANDO RETOMAR...")
        campaign.resume()
        task2 = process_campaign.delay(str(campaign.id))
        print(f"✅ Campanha retomada - Status: {campaign.status}")
        print(f"✅ Nova task disparada: {task2.id}")
        
        print("⏳ Aguardando 3 segundos...")
        time.sleep(3)
        
        campaign.refresh_from_db()
        print(f"📊 Após retomar:")
        print(f"   Enviadas: {campaign.messages_sent}/{campaign.total_contacts}")
    
    # 8. Verificar logs
    print("\n8️⃣ VERIFICANDO LOGS...")
    logs = CampaignLog.objects.filter(campaign=campaign).order_by('created_at')
    print(f"Total de logs: {logs.count()}")
    
    for log in logs[:15]:
        severity_icon = {
            'info': '📘',
            'warning': '⚠️',
            'error': '❌',
            'critical': '🔴'
        }.get(log.severity, '📄')
        
        print(f"   {severity_icon} [{log.log_type}] {log.message}")
    
    # 9. Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO FINAL")
    print("="*80)
    
    campaign.refresh_from_db()
    print(f"""
Campanha: {campaign.name}
Status: {campaign.status}
Total de Contatos: {campaign.total_contacts}

📨 Mensagens:
   Enviadas: {campaign.messages_sent}
   Entregues: {campaign.messages_delivered}
   Lidas: {campaign.messages_read}
   Falhas: {campaign.messages_failed}

📋 Contatos:
   Pendentes: {CampaignContact.objects.filter(campaign=campaign, status='pending').count()}
   Enviados: {CampaignContact.objects.filter(campaign=campaign, status='sent').count()}
   Entregues: {CampaignContact.objects.filter(campaign=campaign, status='delivered').count()}
   Falhas: {CampaignContact.objects.filter(campaign=campaign, status='failed').count()}

📝 Logs: {CampaignLog.objects.filter(campaign=campaign).count()} registros
    """)
    
    print("="*80)
    print("✅ TESTE COMPLETO!")
    print("="*80 + "\n")

if __name__ == '__main__':
    test_campaign_flow()




