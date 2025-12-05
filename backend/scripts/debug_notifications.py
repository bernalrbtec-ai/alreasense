#!/usr/bin/env python
"""
Script de diagnóstico para verificar notificações diárias.

Uso:
    python manage.py shell < scripts/debug_notifications.py
    ou
    python scripts/debug_notifications.py
"""
import os
import sys
import django
from datetime import time as dt_time
from django.utils import timezone

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences
from apps.authn.models import User

def debug_notifications():
    """Diagnóstico completo de notificações"""
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE NOTIFICAÇÕES DIÁRIAS")
    print("=" * 80)
    
    # 1. Verificar preferências
    print("\n📋 1. PREFERÊNCIAS DE NOTIFICAÇÃO:")
    print("-" * 80)
    
    all_prefs = UserNotificationPreferences.objects.all().select_related('user', 'tenant')
    print(f"Total de preferências: {all_prefs.count()}")
    
    for pref in all_prefs:
        print(f"\n  👤 Usuário: {pref.user.email} (ID: {pref.user.id})")
        print(f"     Tenant: {pref.tenant.name}")
        print(f"     Daily Summary:")
        print(f"       - Habilitado: {pref.daily_summary_enabled}")
        print(f"       - Horário: {pref.daily_summary_time}")
        print(f"       - Último envio: {pref.last_daily_summary_sent_date}")
        print(f"     Agenda Reminder:")
        print(f"       - Habilitado: {pref.agenda_reminder_enabled}")
        print(f"       - Horário: {pref.agenda_reminder_time}")
        print(f"     Canais:")
        print(f"       - WhatsApp: {pref.notify_via_whatsapp}")
        print(f"       - WebSocket: {pref.notify_via_websocket}")
        print(f"       - Email: {pref.notify_via_email}")
        print(f"     Usuário tem telefone: {bool(pref.user.phone)}")
        if pref.user.phone:
            print(f"     Telefone: {pref.user.phone}")
    
    # 2. Verificar usuários com notificações habilitadas
    print("\n📋 2. USUÁRIOS COM NOTIFICAÇÕES HABILITADAS:")
    print("-" * 80)
    
    daily_enabled = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user', 'tenant')
    
    print(f"Daily Summary habilitado: {daily_enabled.count()}")
    for pref in daily_enabled:
        print(f"  - {pref.user.email}: {pref.daily_summary_time}")
    
    agenda_enabled = UserNotificationPreferences.objects.filter(
        agenda_reminder_enabled=True,
        agenda_reminder_time__isnull=False
    ).select_related('user', 'tenant')
    
    print(f"\nAgenda Reminder habilitado: {agenda_enabled.count()}")
    for pref in agenda_enabled:
        print(f"  - {pref.user.email}: {pref.agenda_reminder_time}")
    
    # 3. Verificar horário atual
    print("\n📋 3. HORÁRIO ATUAL:")
    print("-" * 80)
    now = timezone.localtime(timezone.now())
    current_time = now.time()
    current_date = now.date()
    print(f"Data/Hora local: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Hora atual: {current_time}")
    print(f"Data atual: {current_date}")
    
    # 4. Verificar se algum usuário está na janela de tempo
    print("\n📋 4. VERIFICAÇÃO DE JANELA DE TEMPO:")
    print("-" * 80)
    
    for pref in daily_enabled:
        summary_time = pref.daily_summary_time
        
        # Calcular janela
        if summary_time.minute >= 2:
            time_window_start = dt_time(summary_time.hour, summary_time.minute - 2)
        elif summary_time.hour > 0:
            time_window_start = dt_time(summary_time.hour - 1, 58 + summary_time.minute)
        else:
            time_window_start = dt_time(23, 58 + summary_time.minute)
        
        if summary_time.minute <= 57:
            time_window_end = dt_time(summary_time.hour, summary_time.minute + 2)
        elif summary_time.hour < 23:
            time_window_end = dt_time(summary_time.hour + 1, summary_time.minute - 58)
        else:
            time_window_end = dt_time(0, summary_time.minute - 58)
        
        # Verificar se está na janela
        if time_window_start <= time_window_end:
            is_in_window = time_window_start <= current_time <= time_window_end
        else:
            is_in_window = current_time >= time_window_start or current_time <= time_window_end
        
        status = "✅ NA JANELA" if is_in_window else "❌ FORA DA JANELA"
        print(f"  {pref.user.email}:")
        print(f"    Horário configurado: {summary_time}")
        print(f"    Janela: {time_window_start} - {time_window_end}")
        print(f"    Hora atual: {current_time}")
        print(f"    Status: {status}")
        if pref.last_daily_summary_sent_date == current_date:
            print(f"    ⚠️ Já enviado hoje ({pref.last_daily_summary_sent_date})")
    
    print("\n" + "=" * 80)
    print("✅ DIAGNÓSTICO CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    debug_notifications()

