#!/usr/bin/env python
"""
Script para verificar o status do sistema de notificações:
- Verifica se o scheduler está rodando
- Verifica preferências de notificação do usuário
- Verifica tarefas de agenda pendentes
- Verifica resumos diários configurados
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta, time
from apps.authn.models import User
from apps.contacts.models import Task
from apps.notifications.models import UserNotificationPreferences, DepartmentNotificationPreferences
from apps.tenancy.models import Tenant
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_scheduler_status():
    """Verifica se o scheduler está rodando"""
    print("\n" + "="*60)
    print("🔍 VERIFICANDO STATUS DO SCHEDULER")
    print("="*60)
    
    # Verificar se o scheduler foi iniciado
    from apps.campaigns.apps import _scheduler_started, _recovery_started
    
    print(f"✅ Scheduler iniciado: {_scheduler_started}")
    print(f"✅ Recovery iniciado: {_recovery_started}")
    
    if not _scheduler_started:
        print("⚠️  ATENÇÃO: O scheduler NÃO foi iniciado!")
        print("   Isso pode acontecer se:")
        print("   - DISABLE_SCHEDULER=1 está definido")
        print("   - O app não foi carregado corretamente")
        print("   - Está rodando em modo de migração")
    else:
        print("✅ Scheduler está rodando")
    
    return _scheduler_started

def check_user_notifications(user_email):
    """Verifica configurações de notificação de um usuário"""
    print("\n" + "="*60)
    print(f"🔍 VERIFICANDO NOTIFICAÇÕES DO USUÁRIO: {user_email}")
    print("="*60)
    
    try:
        user = User.objects.get(email=user_email)
        print(f"✅ Usuário encontrado: {user.email} (ID: {user.id})")
        print(f"   Tenant: {user.tenant.name if user.tenant else 'N/A'}")
        print(f"   Ativo: {user.is_active}")
        
        # Verificar preferências de usuário
        try:
            pref = UserNotificationPreferences.objects.get(user=user)
            print(f"\n📋 PREFERÊNCIAS DE USUÁRIO:")
            print(f"   Resumo diário habilitado: {pref.daily_summary_enabled}")
            print(f"   Horário do resumo: {pref.daily_summary_time}")
            print(f"   Último resumo enviado: {pref.last_daily_summary_sent_date}")
            print(f"   Lembrete de agenda habilitado: {pref.agenda_reminder_enabled}")
            print(f"   Horário do lembrete: {pref.agenda_reminder_time}")
            
            # Verificar se está no horário
            local_now = timezone.localtime(timezone.now())
            current_time = local_now.time()
            current_date = local_now.date()
            
            print(f"\n⏰ HORA ATUAL:")
            print(f"   UTC: {timezone.now().strftime('%H:%M:%S')}")
            print(f"   Local: {local_now.strftime('%H:%M:%S')}")
            print(f"   Data: {current_date}")
            
            # Verificar resumo diário
            if pref.daily_summary_enabled and pref.daily_summary_time:
                from apps.notifications.services import calculate_time_window
                time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
                
                print(f"\n📊 RESUMO DIÁRIO:")
                print(f"   Configurado para: {pref.daily_summary_time}")
                print(f"   Janela de verificação: {time_window_start} - {time_window_end}")
                print(f"   Está na janela: {time_window_start <= current_time <= time_window_end}")
                print(f"   Último envio: {pref.last_daily_summary_sent_date}")
                print(f"   Já enviado hoje: {pref.last_daily_summary_sent_date == current_date}")
                
                if pref.last_daily_summary_sent_date == current_date:
                    print("   ⚠️  Resumo já foi enviado hoje!")
                elif time_window_start <= current_time <= time_window_end:
                    print("   ✅ Está no horário de envio!")
                else:
                    print(f"   ⏳ Aguardando horário (próxima janela em ~{((time_window_start.hour * 60 + time_window_start.minute) - (current_time.hour * 60 + current_time.minute)) % 1440} minutos)")
            
            # Verificar lembrete de agenda
            if pref.agenda_reminder_enabled and pref.agenda_reminder_time:
                print(f"\n📅 LEMBRETE DE AGENDA:")
                print(f"   Configurado para: {pref.agenda_reminder_time}")
                print(f"   ⚠️  NOTA: Lembretes de agenda são enviados 15 minutos ANTES do compromisso")
                print(f"   (Não baseado no horário configurado aqui)")
            
        except UserNotificationPreferences.DoesNotExist:
            print("⚠️  Nenhuma preferência de notificação encontrada para este usuário!")
            print("   Criando preferências padrão...")
            pref = UserNotificationPreferences.objects.create(
                user=user,
                tenant=user.tenant,
                daily_summary_enabled=False,
                agenda_reminder_enabled=False
            )
            print(f"   ✅ Preferências criadas (desabilitadas por padrão)")
        
        # Verificar tarefas de agenda
        print(f"\n📋 TAREFAS DE AGENDA:")
        now = timezone.now()
        local_now = timezone.localtime(now)
        
        # Tarefas futuras (próximas 24h)
        upcoming_tasks = Task.objects.filter(
            assigned_to=user,
            tenant=user.tenant,
            task_type='agenda',
            status__in=['pending', 'in_progress'],
            due_date__gte=now,
            due_date__lte=now + timedelta(hours=24)
        ).order_by('due_date')
        
        print(f"   Tarefas nas próximas 24h: {upcoming_tasks.count()}")
        
        for task in upcoming_tasks[:5]:
            local_due = timezone.localtime(task.due_date)
            minutes_until = (task.due_date - now).total_seconds() / 60
            print(f"   - {task.title}")
            print(f"     Data/Hora: {local_due.strftime('%d/%m/%Y %H:%M')}")
            print(f"     Em: {int(minutes_until)} minutos")
            print(f"     Notificada: {task.notification_sent}")
            print(f"     Status: {task.status}")
        
        # Tarefas na janela de lembrete (15 minutos antes)
        minutes_before = 15
        notification_window_start = now + timedelta(minutes=minutes_before - 5)
        notification_window_end = now + timedelta(minutes=minutes_before + 5)
        
        reminder_tasks = Task.objects.filter(
            assigned_to=user,
            tenant=user.tenant,
            task_type='agenda',
            status__in=['pending', 'in_progress'],
            due_date__gte=notification_window_start,
            due_date__lte=notification_window_end,
            notification_sent=False
        )
        
        print(f"\n   Tarefas na janela de lembrete (15min antes): {reminder_tasks.count()}")
        if reminder_tasks.exists():
            print("   ⚠️  Estas tarefas DEVEM receber notificação agora!")
            for task in reminder_tasks:
                local_due = timezone.localtime(task.due_date)
                print(f"   - {task.title} ({local_due.strftime('%d/%m/%Y %H:%M')})")
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ Usuário não encontrado: {user_email}")
        return False
    except Exception as e:
        print(f"❌ Erro ao verificar usuário: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_all_active_preferences():
    """Lista todas as preferências ativas"""
    print("\n" + "="*60)
    print("🔍 TODAS AS PREFERÊNCIAS ATIVAS")
    print("="*60)
    
    local_now = timezone.localtime(timezone.now())
    current_time = local_now.time()
    current_date = local_now.date()
    
    # Resumos diários de usuários
    daily_summaries = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False,
        tenant__status='active',
        user__is_active=True
    ).select_related('user', 'tenant')
    
    print(f"\n📊 RESUMOS DIÁRIOS DE USUÁRIOS: {daily_summaries.count()}")
    for pref in daily_summaries[:10]:
        from apps.notifications.services import calculate_time_window
        time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
        in_window = time_window_start <= current_time <= time_window_end
        already_sent = pref.last_daily_summary_sent_date == current_date
        
        status = "✅ PRONTO" if (in_window and not already_sent) else ("⏳ AGUARDANDO" if not already_sent else "✅ JÁ ENVIADO")
        print(f"   {status} - {pref.user.email} ({pref.tenant.name}) - {pref.daily_summary_time} - Último: {pref.last_daily_summary_sent_date}")
    
    # Lembretes de agenda de usuários
    agenda_reminders = UserNotificationPreferences.objects.filter(
        agenda_reminder_enabled=True,
        agenda_reminder_time__isnull=False,
        tenant__status='active',
        user__is_active=True
    ).select_related('user', 'tenant')
    
    print(f"\n📅 LEMBRETES DE AGENDA DE USUÁRIOS: {agenda_reminders.count()}")
    for pref in agenda_reminders[:10]:
        print(f"   - {pref.user.email} ({pref.tenant.name}) - {pref.agenda_reminder_time}")

def main():
    """Função principal"""
    print("\n" + "="*60)
    print("🔍 DIAGNÓSTICO DO SISTEMA DE NOTIFICAÇÕES")
    print("="*60)
    
    # 1. Verificar scheduler
    scheduler_running = check_scheduler_status()
    
    # 2. Verificar usuário específico
    user_email = os.environ.get('USER_EMAIL', 'paulo.bernal@rbtec.com.br')
    check_user_notifications(user_email)
    
    # 3. Listar todas as preferências ativas
    check_all_active_preferences()
    
    # 4. Resumo final
    print("\n" + "="*60)
    print("📋 RESUMO")
    print("="*60)
    
    if not scheduler_running:
        print("❌ SCHEDULER NÃO ESTÁ RODANDO!")
        print("   Ação necessária: Verificar por que o scheduler não iniciou")
    else:
        print("✅ Scheduler está rodando")
    
    print("\n💡 DICAS:")
    print("   - Se o scheduler não está rodando, verifique:")
    print("     * Variável DISABLE_SCHEDULER não está definida como '1'")
    print("     * O app 'campaigns' está instalado no INSTALLED_APPS")
    print("     * Não está rodando em modo de migração")
    print("   - Se as notificações não estão sendo enviadas:")
    print("     * Verifique se as preferências estão habilitadas")
    print("     * Verifique se está no horário configurado")
    print("     * Verifique se já foi enviado hoje (last_daily_summary_sent_date)")
    print("     * Verifique se há tarefas de agenda com notification_sent=False")

if __name__ == '__main__':
    main()

