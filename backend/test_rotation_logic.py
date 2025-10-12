#!/usr/bin/env python
"""
Teste completo da lógica de rotação de instâncias
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.campaigns.models import Campaign
from apps.campaigns.services import RotationService
from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant

print("\n" + "="*70)
print("🧪 TESTE - LÓGICA DE ROTAÇÃO")
print("="*70)

# Buscar tenant de teste
tenant = Tenant.objects.filter(name='Teste Campanhas').first()
if not tenant:
    print("❌ Tenant 'Teste Campanhas' não encontrado")
    print("   Execute: docker-compose exec backend python create_test_client.py")
    exit(1)

print(f"\n✅ Tenant: {tenant.name}")

# Criar instâncias de teste (simuladas)
print("\n1️⃣ Criando instâncias de teste...")

instances = []
for i, name in enumerate(['Instância A', 'Instância B', 'Instância C']):
    instance, created = WhatsAppInstance.objects.get_or_create(
        tenant=tenant,
        friendly_name=name,
        defaults={
            'instance_name': f'test-instance-{i}',
            'connection_state': 'open',
            'status': 'active',
            'health_score': 100 - (i * 5),  # 100, 95, 90
            'msgs_sent_today': i * 10,  # 0, 10, 20
        }
    )
    
    if not created:
        # Atualizar se já existe
        instance.connection_state = 'open'
        instance.status = 'active'
        instance.health_score = 100 - (i * 5)
        instance.msgs_sent_today = i * 10
        instance.save()
    
    instances.append(instance)
    print(f"   ✅ {name}: Health={instance.health_score}, Enviadas={instance.msgs_sent_today}")

# Criar campanha de teste
print("\n2️⃣ Criando campanhas de teste...")

campaigns = {}
for mode in ['round_robin', 'balanced', 'intelligent']:
    campaign, created = Campaign.objects.get_or_create(
        tenant=tenant,
        name=f'Teste Rotação - {mode.upper()}',
        defaults={
            'rotation_mode': mode,
            'status': 'running',
            'interval_min': 3,
            'interval_max': 8,
            'daily_limit_per_instance': 100,
            'pause_on_health_below': 50
        }
    )
    
    if not created:
        campaign.rotation_mode = mode
        campaign.status = 'running'
        campaign.save()
    
    # Associar instâncias
    campaign.instances.set(instances)
    
    campaigns[mode] = campaign
    print(f"   ✅ Campanha criada: {mode}")

# Testar cada modo de rotação
print("\n" + "="*70)
print("🔄 TESTANDO MODOS DE ROTAÇÃO")
print("="*70)

for mode, campaign in campaigns.items():
    print(f"\n📊 Modo: {mode.upper()} ({campaign.get_rotation_mode_display()})")
    print("-" * 70)
    
    service = RotationService(campaign)
    
    # Selecionar 5 vezes para ver o padrão
    selections = []
    for i in range(5):
        instance = service.select_next_instance()
        if instance:
            selections.append(instance.friendly_name)
            print(f"   {i+1}. {instance.friendly_name} (Health: {instance.health_score}, Enviadas: {instance.msgs_sent_today})")
        else:
            print(f"   {i+1}. ❌ Nenhuma instância disponível")
    
    # Mostrar padrão
    if selections:
        print(f"\n   📈 Padrão: {' → '.join(selections)}")
    
    # Explicação
    if mode == 'round_robin':
        print("   💡 Round Robin: Rotação sequencial fixa")
    elif mode == 'balanced':
        print("   💡 Balanceado: Sempre escolhe a com MENOS mensagens enviadas")
    else:
        print("   💡 Inteligente: Calcula peso baseado em health (70%) + disponibilidade (30%)")

# Testar limites
print("\n" + "="*70)
print("🚫 TESTANDO LIMITES")
print("="*70)

print("\n1️⃣ Testando limite diário...")
campaign = campaigns['intelligent']
test_instance = instances[0]

# Simular limite atingido
test_instance.msgs_sent_today = 100
test_instance.save()

service = RotationService(campaign)
instance = service.select_next_instance()

if instance and instance.id != test_instance.id:
    print(f"✅ Instância com limite ignorada corretamente")
    print(f"   Selecionada: {instance.friendly_name}")
else:
    print(f"⚠️ Instância: {instance.friendly_name if instance else 'Nenhuma'}")

# Resetar
test_instance.msgs_sent_today = 0
test_instance.save()

print("\n2️⃣ Testando health baixo...")
test_instance.health_score = 30
test_instance.save()

instance = service.select_next_instance()

if instance and instance.id != test_instance.id:
    print(f"✅ Instância com health baixo ignorada corretamente")
    print(f"   Selecionada: {instance.friendly_name}")
else:
    print(f"⚠️ Instância: {instance.friendly_name if instance else 'Nenhuma'}")

# Resetar
test_instance.health_score = 100
test_instance.save()

print("\n3️⃣ Testando instância desconectada...")
test_instance.connection_state = 'close'
test_instance.save()

instance = service.select_next_instance()

if instance and instance.id != test_instance.id:
    print(f"✅ Instância desconectada ignorada corretamente")
    print(f"   Selecionada: {instance.friendly_name}")
else:
    print(f"⚠️ Instância: {instance.friendly_name if instance else 'Nenhuma'}")

# Resetar
test_instance.connection_state = 'open'
test_instance.save()

# Verificar logs
print("\n" + "="*70)
print("📋 LOGS GERADOS")
print("="*70)

from apps.campaigns.models import CampaignLog

for mode, campaign in campaigns.items():
    logs_count = CampaignLog.objects.filter(campaign=campaign).count()
    print(f"\n{mode.upper()}: {logs_count} logs")
    
    # Mostrar últimos 3
    logs = CampaignLog.objects.filter(campaign=campaign).order_by('-created_at')[:3]
    for log in logs:
        print(f"   [{log.severity}] {log.log_type}: {log.message}")

print("\n" + "="*70)
print("✅ TESTE CONCLUÍDO!")
print("="*70)
print(f"\n📊 Resumo:")
print(f"   Instâncias criadas: {len(instances)}")
print(f"   Campanhas criadas: {len(campaigns)}")
print(f"   Total de logs: {CampaignLog.objects.count()}")
print("\n")



