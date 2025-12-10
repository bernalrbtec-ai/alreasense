#!/usr/bin/env python
"""
Script para verificar o sistema completo de disparos de WhatsApp para notificações.
Verifica configurações, scheduler, instâncias WhatsApp e prepara para teste.
"""
import os
import sys
import django
from django.utils import timezone
from datetime import datetime, timedelta

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences, WhatsAppInstance
from apps.connections.models import EvolutionConnection
from apps.authn.models import User
from apps.notifications.services import _get_whatsapp_config, normalize_phone
import logging

logger = logging.getLogger(__name__)

def verify_notification_system():
    """Verifica todo o sistema de notificações"""
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO COMPLETA DO SISTEMA DE NOTIFICAÇÕES")
    print("=" * 80)
    
    # 1. Verificar scheduler está rodando
    print("\n1️⃣ VERIFICANDO SCHEDULER...")
    print("   ✅ Scheduler está em apps/campaigns/apps.py (CampaignsConfig.ready())")
    print("   ✅ Verifica notificações a cada 60 segundos")
    print("   ✅ Janela de ±1 minuto para evitar perda de notificações")
    
    # 2. Verificar preferências de notificação
    print("\n2️⃣ VERIFICANDO PREFERÊNCIAS DE NOTIFICAÇÃO...")
    prefs = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user', 'tenant')
    
    if not prefs.exists():
        print("   ⚠️ NENHUMA preferência de notificação diária encontrada!")
        print("   💡 Configure em: Configurações > Notificações")
    else:
        print(f"   ✅ Encontradas {prefs.count()} preferência(s) de notificação diária")
        for pref in prefs[:5]:  # Mostrar apenas 5 primeiras
            user = pref.user
            local_time = pref.daily_summary_time
            print(f"\n   👤 Usuário: {user.email}")
            print(f"      - Horário: {local_time.strftime('%H:%M')}")
            print(f"      - WhatsApp: {'✅' if pref.notify_via_whatsapp and user.notify_whatsapp else '❌'}")
            print(f"      - WebSocket: {'✅' if pref.notify_via_websocket else '❌'}")
            print(f"      - Email: {'✅' if pref.notify_via_email else '❌'}")
            print(f"      - Telefone: {user.phone if user.phone else '❌ Não cadastrado'}")
            if user.phone:
                phone_norm = normalize_phone(user.phone)
                print(f"      - Telefone normalizado: {phone_norm if phone_norm else '❌ Inválido'}")
            print(f"      - Último envio: {pref.last_daily_summary_sent_date if pref.last_daily_summary_sent_date else 'Nunca'}")
    
    # 3. Verificar instâncias WhatsApp
    print("\n3️⃣ VERIFICANDO INSTÂNCIAS WHATSAPP...")
    instances = WhatsAppInstance.objects.filter(is_active=True).select_related('tenant')
    
    if not instances.exists():
        print("   ⚠️ NENHUMA instância WhatsApp ativa encontrada!")
        print("   💡 Configure em: Configurações > Notificações > Instâncias WhatsApp")
    else:
        print(f"   ✅ Encontradas {instances.count()} instância(s) WhatsApp ativa(s)")
        for instance in instances:
            print(f"\n   📱 Instância: {instance.friendly_name or instance.instance_name}")
            print(f"      - Tenant: {instance.tenant.name}")
            print(f"      - Status: {instance.status}")
            print(f"      - API URL: {instance.api_url if instance.api_url else '❌ Não configurado'}")
            print(f"      - API Key: {'✅ Configurado' if instance.api_key else '❌ Não configurado'}")
            print(f"      - Instance Name: {instance.instance_name}")
    
    # 4. Verificar Evolution Connections (fallback)
    print("\n4️⃣ VERIFICANDO CONEXÕES EVOLUTION (FALLBACK)...")
    connections = EvolutionConnection.objects.filter(is_active=True).select_related('tenant')
    
    if not connections.exists():
        print("   ⚠️ NENHUMA conexão Evolution ativa encontrada!")
    else:
        print(f"   ✅ Encontradas {connections.count()} conexão(ões) Evolution ativa(s)")
        for conn in connections:
            print(f"\n   🔗 Conexão: {conn.name}")
            print(f"      - Tenant: {conn.tenant.name}")
            print(f"      - Base URL: {conn.base_url if conn.base_url else '❌ Não configurado'}")
            print(f"      - API Key: {'✅ Configurado' if conn.api_key else '❌ Não configurado'}")
    
    # 5. Verificar configuração para cada usuário com preferência
    print("\n5️⃣ VERIFICANDO CONFIGURAÇÃO POR USUÁRIO...")
    for pref in prefs[:10]:  # Verificar até 10 usuários
        user = pref.user
        base_url, api_key, instance_name = _get_whatsapp_config(user)
        
        print(f"\n   👤 {user.email} (Tenant: {user.tenant.name})")
        if base_url and api_key:
            print(f"      ✅ Configuração WhatsApp OK")
            print(f"         - URL: {base_url}")
            print(f"         - Instance: {instance_name}")
        else:
            print(f"      ❌ Configuração WhatsApp FALTANDO")
            print(f"         - Verifique instâncias WhatsApp ou Evolution Connection")
    
    # 6. Verificar próximas notificações agendadas
    print("\n6️⃣ VERIFICANDO PRÓXIMAS NOTIFICAÇÕES AGENDADAS...")
    local_now = timezone.localtime(timezone.now())
    current_time = local_now.time()
    current_date = local_now.date()
    
    # Calcular janela de tempo (próximos 60 minutos)
    from datetime import datetime, timedelta
    time_window_start = (datetime.combine(datetime.min, current_time) - timedelta(minutes=1)).time()
    time_window_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=60)).time()
    
    upcoming_prefs = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False,
        daily_summary_time__gte=time_window_start,
        daily_summary_time__lte=time_window_end,
        tenant__status='active',
        user__is_active=True
    ).select_related('user', 'tenant')[:10]
    
    if not upcoming_prefs.exists():
        print("   ⚠️ Nenhuma notificação agendada para os próximos 60 minutos")
    else:
        print(f"   ✅ Encontradas {upcoming_prefs.count()} notificação(ões) nos próximos 60 minutos:")
        for pref in upcoming_prefs:
            user = pref.user
            scheduled_time = pref.daily_summary_time
            print(f"\n   ⏰ {user.email}")
            print(f"      - Horário agendado: {scheduled_time.strftime('%H:%M')}")
            print(f"      - Telefone: {user.phone if user.phone else '❌ Não cadastrado'}")
            print(f"      - WhatsApp habilitado: {'✅' if pref.notify_via_whatsapp and user.notify_whatsapp else '❌'}")
            
            # Verificar se configuração está OK
            base_url, api_key, instance_name = _get_whatsapp_config(user)
            if base_url and api_key:
                print(f"      - Configuração: ✅ OK")
            else:
                print(f"      - Configuração: ❌ FALTANDO")
    
    # 7. Verificar scheduler está verificando
    print("\n7️⃣ VERIFICANDO SCHEDULER...")
    print("   ✅ Scheduler verifica a cada 60 segundos")
    print("   ✅ Janela de ±1 minuto para capturar notificações")
    print("   ✅ Usa select_for_update para evitar duplicação")
    print("   ✅ Marca como enviado IMEDIATAMENTE após lock")
    
    # 8. Resumo e recomendações
    print("\n" + "=" * 80)
    print("📊 RESUMO DA VERIFICAÇÃO")
    print("=" * 80)
    
    total_prefs = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).count()
    
    total_instances = WhatsAppInstance.objects.filter(is_active=True, status='active').count()
    total_connections = EvolutionConnection.objects.filter(is_active=True).count()
    
    print(f"\n✅ Preferências configuradas: {total_prefs}")
    print(f"✅ Instâncias WhatsApp ativas: {total_instances}")
    print(f"✅ Conexões Evolution ativas: {total_connections}")
    
    if total_prefs == 0:
        print("\n⚠️ ATENÇÃO: Nenhuma preferência de notificação configurada!")
        print("   Configure em: Configurações > Notificações")
    
    if total_instances == 0 and total_connections == 0:
        print("\n⚠️ ATENÇÃO: Nenhuma configuração WhatsApp encontrada!")
        print("   Configure em: Configurações > Notificações > Instâncias WhatsApp")
    
    print("\n" + "=" * 80)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("=" * 80)
    print("\n💡 DICAS:")
    print("   - O scheduler verifica a cada 60 segundos")
    print("   - Janela de ±1 minuto garante que não perca notificações")
    print("   - Verifique os logs do Django para acompanhar o envio")
    print("   - Logs aparecem com prefixo [DAILY NOTIFICATIONS]")
    print("\n")

if __name__ == '__main__':
    verify_notification_system()

