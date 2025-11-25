#!/usr/bin/env python
"""
Script para forçar o envio de notificações manualmente:
- Envia resumo diário para usuários que estão no horário
- Envia lembretes de agenda que estão na janela
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from apps.authn.models import User
from apps.contacts.models import Task
from apps.notifications.models import UserNotificationPreferences, DepartmentNotificationPreferences
from apps.notifications.services import calculate_time_window, send_notifications
import logging

def format_daily_summary_message(user, tasks_by_status, current_date):
    """Formata mensagem de resumo diário para WhatsApp"""
    from datetime import datetime
    
    pending = tasks_by_status['pending']
    in_progress = tasks_by_status['in_progress']
    completed = tasks_by_status['completed']
    overdue = tasks_by_status['overdue']
    
    # Formatar data
    date_str = current_date.strftime('%d/%m/%Y')
    
    message = f"📊 *Resumo Diário - {date_str}*\n\n"
    message += f"Olá, {user.first_name or user.email.split('@')[0]}!\n\n"
    
    # Tarefas atrasadas (prioridade)
    if overdue:
        message += f"⚠️ *Tarefas Atrasadas ({len(overdue)}):*\n"
        for task in overdue[:5]:
            message += f"   • {task.title}\n"
        message += "\n"
    
    # Tarefas pendentes
    if pending:
        message += f"📋 *Pendentes ({len(pending)}):*\n"
        for task in pending[:5]:
            message += f"   • {task.title}\n"
        message += "\n"
    
    # Tarefas em progresso
    if in_progress:
        message += f"🔄 *Em Progresso ({len(in_progress)}):*\n"
        for task in in_progress[:5]:
            message += f"   • {task.title}\n"
        message += "\n"
    
    # Tarefas concluídas
    if completed:
        message += f"✅ *Concluídas ({len(completed)}):*\n"
        for task in completed[:5]:
            message += f"   • {task.title}\n"
        message += "\n"
    
    # Mensagem motivacional
    total = len(pending) + len(in_progress) + len(completed)
    if overdue:
        message += "💡 *Dica:* Priorize as tarefas atrasadas para manter tudo em dia!"
    elif pending:
        message += "✨ *Bom dia!* Você tem um dia produtivo pela frente!"
    elif completed_count == total and total > 0:
        message += "🌟 *Parabéns!* Você concluiu todas as tarefas de hoje!"
    
    return message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def force_send_daily_summaries(force_all=False):
    """Força o envio de resumos diários para usuários que estão no horário ou todos se force_all=True"""
    print("\n" + "="*60)
    print("📊 FORÇANDO ENVIO DE RESUMOS DIÁRIOS")
    print("="*60)
    
    local_now = timezone.localtime(timezone.now())
    current_time = local_now.time()
    current_date = local_now.date()
    
    from django.db import transaction
    
    # Buscar preferências que estão no horário OU todas se force_all
    if force_all:
        # Buscar todas as preferências ativas (sem filtro de data para forçar)
        print(f"⚠️  MODO FORÇADO: Enviando para TODAS as preferências ativas")
        
        # Primeiro, verificar quantas existem sem filtro
        all_prefs = UserNotificationPreferences.objects.filter(
            daily_summary_enabled=True,
            daily_summary_time__isnull=False,
            tenant__status='active',
            user__is_active=True
        )
        print(f"📊 Total de preferências ativas encontradas: {all_prefs.count()}")
        for p in all_prefs:
            print(f"   - {p.user.email}: horário={p.daily_summary_time}, último_envio={p.last_daily_summary_sent_date}")
        
        preference_ids = []
        with transaction.atomic():
            # Remover filtro de data para forçar envio
            preferences_locked = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                daily_summary_enabled=True,
                daily_summary_time__isnull=False,
                tenant__status='active',
                user__is_active=True
            ).values_list('id', flat=True)
            
            preference_ids = list(preferences_locked)
    else:
        # Buscar apenas as que estão no horário
        time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
        
        preference_ids = []
        with transaction.atomic():
            preferences_locked = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                daily_summary_enabled=True,
                daily_summary_time__isnull=False,
                daily_summary_time__gte=time_window_start,
                daily_summary_time__lte=time_window_end,
                tenant__status='active',
                user__is_active=True
            ).values_list('id', flat=True)
            
            preference_ids = list(preferences_locked)
    
    preferences = []
    if preference_ids:
        preferences = list(
            UserNotificationPreferences.objects.filter(id__in=preference_ids)
            .select_related('user', 'tenant', 'user__tenant')
        )
    
    print(f"📋 Encontradas {len(preferences)} preferências no horário")
    
    count = 0
    for pref in preferences:
        try:
            with transaction.atomic():
                # Em modo forçado, ignorar verificação de data
                if force_all:
                    locked_pref_id = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                        id=pref.id
                    ).values_list('id', flat=True).first()
                else:
                    locked_pref_id = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
                        id=pref.id,
                        last_daily_summary_sent_date__lt=current_date
                    ).values_list('id', flat=True).first()
                
                if not locked_pref_id:
                    print(f"⏭️  {pref.user.email} - Está sendo processado por outra instância (lock não adquirido)")
                    continue
                
                locked_pref = UserNotificationPreferences.objects.select_related('user', 'tenant', 'user__tenant').get(id=locked_pref_id)
                locked_pref.last_daily_summary_sent_date = current_date
                locked_pref.save(update_fields=['last_daily_summary_sent_date'])
                pref = locked_pref
            
            # Enviar resumo - usar a função do scheduler
            from apps.campaigns.apps import CampaignsConfig
            # A função send_user_daily_summary está dentro de check_scheduled_campaigns
            # Vamos chamar diretamente a lógica do scheduler
            from apps.contacts.models import Task
            from apps.notifications.services import send_notifications
            
            # Buscar tarefas do usuário
            tasks = Task.objects.filter(
                assigned_to=pref.user,
                tenant=pref.user.tenant,
                task_type='task',
                include_in_notifications=True
            ).exclude(
                status__in=['cancelled']
            ).select_related('department', 'created_by', 'tenant', 'assigned_to').prefetch_related('related_contacts')
            
            # Aplicar filtros baseados nas preferências
            if not pref.notify_pending:
                tasks = tasks.exclude(status='pending')
            if not pref.notify_in_progress:
                tasks = tasks.exclude(status='in_progress')
            if not pref.notify_completed:
                tasks = tasks.exclude(status='completed')
            
            # Filtrar tarefas do dia
            local_now = timezone.localtime(timezone.now())
            tasks_today = tasks.filter(
                due_date__date=current_date
            )
            
            # Tarefas atrasadas
            overdue_tasks = tasks.filter(
                due_date__lt=local_now,
                status__in=['pending', 'in_progress']
            )
            
            # Agrupar por status
            tasks_by_status = {
                'pending': list(tasks_today.filter(status='pending')[:10]),
                'in_progress': list(tasks_today.filter(status='in_progress')[:10]),
                'completed': list(tasks_today.filter(status='completed')[:10]),
                'overdue': list(overdue_tasks[:10]),
            }
            
            # Verificar se há tarefas
            total_tasks = sum(len(tasks) for tasks in tasks_by_status.values())
            if total_tasks == 0:
                print(f"⏭️  {pref.user.email} - Nenhuma tarefa para notificar hoje")
                continue
            
            # Formatar mensagem
            message = format_daily_summary_message(pref.user, tasks_by_status, current_date)
            
            if not message or len(message.strip()) == 0:
                print(f"⚠️  {pref.user.email} - Mensagem vazia, pulando")
                continue
            
            # Enviar notificações
            notifications_sent, notifications_failed = send_notifications(
                user=pref.user,
                preferences=pref,
                message=message,
                notification_type='daily_summary',
                data={
                    'date': current_date.isoformat(),
                    'tasks': {
                        'pending': len(tasks_by_status['pending']),
                        'in_progress': len(tasks_by_status['in_progress']),
                        'completed': len(tasks_by_status['completed']),
                        'overdue': len(tasks_by_status['overdue']),
                    }
                },
                context_name=''
            )
            
            if notifications_sent > 0:
                count += 1
                print(f"✅ Resumo enviado para {pref.user.email} ({notifications_sent} canal(is))")
            else:
                print(f"⚠️  {pref.user.email} - Falha ao enviar ({notifications_failed} falhou(aram))")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar resumo para {pref.user.email}: {e}", exc_info=True)
    
    print(f"\n✅ {count} resumo(s) enviado(s)")
    return count

def force_send_agenda_reminders():
    """Força o envio de lembretes de agenda que estão na janela"""
    print("\n" + "="*60)
    print("📅 FORÇANDO ENVIO DE LEMBRETES DE AGENDA")
    print("="*60)
    
    now = timezone.now()
    minutes_before = 15
    notification_window_start = now + timedelta(minutes=minutes_before - 5)
    notification_window_end = now + timedelta(minutes=minutes_before + 5)
    
    from django.db import transaction
    
    task_ids_reminder = []
    with transaction.atomic():
        tasks_reminder = Task.objects.select_for_update(skip_locked=True).filter(
            due_date__gte=notification_window_start,
            due_date__lte=notification_window_end,
            status__in=['pending', 'in_progress'],
            notification_sent=False,
            task_type='agenda'
        ).exclude(
            status__in=['completed', 'cancelled']
        ).values_list('id', flat=True)
        
        task_ids_reminder = list(tasks_reminder)
    
    tasks_reminder_list = []
    if task_ids_reminder:
        tasks_reminder_list = list(
            Task.objects.filter(id__in=task_ids_reminder)
            .select_related('assigned_to', 'created_by', 'tenant', 'department')
        )
    
    print(f"📋 Encontradas {len(tasks_reminder_list)} tarefas na janela de lembrete")
    
    count = 0
    for task in tasks_reminder_list:
        try:
            with transaction.atomic():
                locked_task_id = Task.objects.select_for_update(skip_locked=True).filter(
                    id=task.id,
                    notification_sent=False
                ).values_list('id', flat=True).first()
                
                if not locked_task_id:
                    print(f"⏭️  Tarefa {task.id} - Já foi notificada ou está sendo processada")
                    continue
                
                locked_task = Task.objects.select_related('assigned_to', 'created_by', 'tenant', 'department').get(id=locked_task_id)
                
                if locked_task.status in ['completed', 'cancelled']:
                    continue
                
                locked_task.notification_sent = True
                locked_task.save(update_fields=['notification_sent'])
                task = locked_task
            
            # Enviar notificação
            from apps.campaigns.apps import CampaignsConfig
            config = CampaignsConfig('apps.campaigns', None)
            
            notification_sent = False
            if task.assigned_to:
                success = config._notify_task_user(task, task.assigned_to, is_reminder=True)
                notification_sent = notification_sent or success
            
            if task.created_by and task.created_by != task.assigned_to:
                success = config._notify_task_user(task, task.created_by, is_reminder=True)
                notification_sent = notification_sent or success
            
            if notification_sent:
                count += 1
                print(f"✅ Lembrete enviado para tarefa: {task.title}")
            else:
                # Resetar se falhou
                Task.objects.filter(id=task.id).update(notification_sent=False)
                print(f"⚠️  Falha ao enviar lembrete para tarefa: {task.title}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar lembrete para tarefa {task.id}: {e}", exc_info=True)
    
    print(f"\n✅ {count} lembrete(s) enviado(s)")
    return count

def main():
    """Função principal"""
    import sys
    
    # Verificar se deve forçar todos (mesmo fora do horário)
    force_all = '--force-all' in sys.argv or '-f' in sys.argv
    
    print("\n" + "="*60)
    print("🚀 FORÇANDO ENVIO DE NOTIFICAÇÕES")
    if force_all:
        print("⚠️  MODO FORÇADO: Enviando mesmo fora do horário configurado")
    print("="*60)
    
    # 1. Resumos diários
    summaries_count = force_send_daily_summaries(force_all=force_all)
    
    # 2. Lembretes de agenda
    reminders_count = force_send_agenda_reminders()
    
    # 3. Resumo final
    print("\n" + "="*60)
    print("📋 RESUMO FINAL")
    print("="*60)
    print(f"✅ Resumos diários enviados: {summaries_count}")
    print(f"✅ Lembretes de agenda enviados: {reminders_count}")
    print(f"✅ Total: {summaries_count + reminders_count}")
    
    if summaries_count == 0 and not force_all:
        print("\n💡 DICA: Use --force-all ou -f para forçar envio mesmo fora do horário")

if __name__ == '__main__':
    main()

