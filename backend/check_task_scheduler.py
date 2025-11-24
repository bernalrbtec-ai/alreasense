"""
Script para verificar se o scheduler de tarefas está funcionando.

Uso:
    python manage.py shell < check_task_scheduler.py
    ou
    python check_task_scheduler.py
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from apps.contacts.models import Task
import threading

def check_scheduler_status():
    """Verifica se o scheduler está rodando e mostra tarefas próximas"""
    print("=" * 60)
    print("🔍 VERIFICAÇÃO DO SCHEDULER DE TAREFAS")
    print("=" * 60)
    
    # 1. Verificar threads ativas
    print("\n📊 Threads ativas:")
    active_threads = [t for t in threading.enumerate() if t.is_alive()]
    scheduler_threads = [t for t in active_threads if 'scheduled' in t.name.lower() or 'campaign' in t.name.lower()]
    
    if scheduler_threads:
        print(f"   ✅ Encontradas {len(scheduler_threads)} thread(s) do scheduler:")
        for t in scheduler_threads:
            print(f"      - {t.name} (ativa: {t.is_alive()})")
    else:
        print("   ⚠️ Nenhuma thread do scheduler encontrada!")
        print("   ℹ️ O scheduler pode não estar rodando. Verifique os logs do Django.")
    
    # 2. Verificar tarefas próximas
    now = timezone.now()
    print(f"\n⏰ Hora atual: {now.strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Tarefas para lembrete (15 min antes)
    minutes_before = 15
    notification_window_start = now + timedelta(minutes=minutes_before - 5)
    notification_window_end = now + timedelta(minutes=minutes_before + 5)
    
    tasks_reminder = Task.objects.filter(
        due_date__gte=notification_window_start,
        due_date__lte=notification_window_end,
        status__in=['pending', 'in_progress'],
        notification_sent=False
    ).exclude(
        status__in=['completed', 'cancelled']
    ).select_related('assigned_to', 'tenant')
    
    # Tarefas chegando agora
    exact_time_window_start = now - timedelta(minutes=5)
    exact_time_window_end = now + timedelta(minutes=1)
    
    tasks_exact = Task.objects.filter(
        due_date__gte=exact_time_window_start,
        due_date__lte=exact_time_window_end,
        status__in=['pending', 'in_progress']
    ).exclude(
        status__in=['completed', 'cancelled']
    ).select_related('assigned_to', 'tenant')
    
    print(f"\n📋 Tarefas para lembrete (15min antes):")
    print(f"   Janela: {notification_window_start.strftime('%H:%M:%S')} - {notification_window_end.strftime('%H:%M:%S')}")
    print(f"   Encontradas: {tasks_reminder.count()}")
    
    if tasks_reminder.exists():
        for task in tasks_reminder:
            print(f"   ✅ {task.title} (ID: {task.id})")
            print(f"      Data/Hora: {task.due_date.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"      Status: {task.status}")
            print(f"      Notificada: {task.notification_sent}")
            print(f"      Atribuído: {task.assigned_to.email if task.assigned_to else 'Ninguém'}")
            print(f"      Tenant: {task.tenant.name if task.tenant else 'N/A'}")
            print()
    
    print(f"\n⏰ Tarefas chegando agora (momento exato):")
    print(f"   Janela: {exact_time_window_start.strftime('%H:%M:%S')} - {exact_time_window_end.strftime('%H:%M:%S')}")
    print(f"   Encontradas: {tasks_exact.count()}")
    
    if tasks_exact.exists():
        for task in tasks_exact:
            print(f"   ✅ {task.title} (ID: {task.id})")
            print(f"      Data/Hora: {task.due_date.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"      Status: {task.status}")
            print(f"      Notificada: {task.notification_sent}")
            print(f"      Atribuído: {task.assigned_to.email if task.assigned_to else 'Ninguém'}")
            print(f"      Tenant: {task.tenant.name if task.tenant else 'N/A'}")
            print()
    
    # 3. Próximas 10 tarefas
    print(f"\n📅 Próximas 10 tarefas nas próximas 24h:")
    upcoming = Task.objects.filter(
        due_date__gte=now,
        due_date__lte=now + timedelta(hours=24),
        status__in=['pending', 'in_progress']
    ).select_related('assigned_to', 'tenant').order_by('due_date')[:10]
    
    if upcoming.exists():
        for task in upcoming:
            print(f"   - {task.title} (ID: {task.id})")
            print(f"     Data/Hora: {task.due_date.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"     Notificada: {task.notification_sent} | Status: {task.status}")
            print()
    else:
        print("   Nenhuma tarefa encontrada")
    
    print("=" * 60)
    print("✅ Verificação concluída")
    print("=" * 60)

if __name__ == '__main__':
    check_scheduler_status()

