#!/usr/bin/env python
"""
Script para diagnosticar por que a notificação não foi enviada.
Verifica scheduler, preferências, janela de tempo e tarefas.
"""
import os
import sys
import django
from django.utils import timezone
from datetime import datetime, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences
from apps.notifications.services import calculate_time_window, check_channels_enabled
from apps.contacts.models import Task
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def diagnose_notification_issue():
    """Diagnostica por que a notificação não foi enviada"""
    
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: Por que a notificação não foi enviada?")
    print("=" * 80)
    
    # 1. Verificar preferência
    print("\n1️⃣ VERIFICANDO PREFERÊNCIA...")
    pref = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user', 'tenant').first()
    
    if not pref:
        print("❌ Nenhuma preferência encontrada!")
        return
    
    user = pref.user
    scheduled_time = pref.daily_summary_time
    last_sent = pref.last_daily_summary_sent_date
    
    print(f"✅ Preferência encontrada:")
    print(f"   - Usuário: {user.email}")
    print(f"   - Horário agendado: {scheduled_time.strftime('%H:%M:%S')}")
    print(f"   - Último envio: {last_sent if last_sent else 'Nunca'}")
    print(f"   - Tenant: {user.tenant.name}")
    print(f"   - Tenant ativo: {'✅' if user.tenant.status == 'active' else '❌'}")
    print(f"   - Usuário ativo: {'✅' if user.is_active else '❌'}")
    
    # 2. Verificar horário atual e janela
    print("\n2️⃣ VERIFICANDO HORÁRIO E JANELA DE TEMPO...")
    local_now = timezone.localtime(timezone.now())
    current_time = local_now.time()
    current_date = local_now.date()
    
    print(f"   - Horário atual (local): {current_time.strftime('%H:%M:%S')}")
    print(f"   - Data atual: {current_date}")
    print(f"   - Horário agendado: {scheduled_time.strftime('%H:%M:%S')}")
    
    # Calcular janela
    time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
    print(f"   - Janela de busca: {time_window_start.strftime('%H:%M:%S')} - {time_window_end.strftime('%H:%M:%S')}")
    
    # Verificar se está na janela
    in_window = time_window_start <= scheduled_time <= time_window_end
    print(f"   - Horário agendado está na janela: {'✅ SIM' if in_window else '❌ NÃO'}")
    
    if not in_window:
        print(f"\n   ⚠️ PROBLEMA ENCONTRADO: Horário agendado ({scheduled_time.strftime('%H:%M:%S')}) não está na janela atual!")
        print(f"      A janela atual é: {time_window_start.strftime('%H:%M:%S')} - {time_window_end.strftime('%H:%M:%S')}")
        print(f"      O scheduler verifica a cada 60 segundos, então a janela muda constantemente.")
        print(f"      Se o horário agendado for 12:10:00, a janela precisa estar entre 12:09:00 e 12:11:00")
    
    # 3. Verificar se já foi enviado hoje
    print("\n3️⃣ VERIFICANDO SE JÁ FOI ENVIADO HOJE...")
    if last_sent == current_date:
        print(f"   ⚠️ PROBLEMA ENCONTRADO: Já foi enviado hoje ({last_sent})!")
        print(f"      O sistema marca como enviado ANTES de processar para evitar duplicação.")
        print(f"      Se houve erro após marcar, a notificação não será reenviada hoje.")
    else:
        print(f"   ✅ Não foi enviado hoje ainda (último envio: {last_sent if last_sent else 'Nunca'})")
    
    # 4. Simular query do scheduler
    print("\n4️⃣ SIMULANDO QUERY DO SCHEDULER...")
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
    
    print(f"   - Preferências encontradas na janela: {len(preference_ids)}")
    
    if pref.id in preference_ids:
        print(f"   ✅ Sua preferência ({pref.id}) SERIA encontrada pelo scheduler")
    else:
        print(f"   ❌ Sua preferência ({pref.id}) NÃO seria encontrada pelo scheduler")
        print(f"      Motivos possíveis:")
        print(f"      1. Horário não está na janela atual")
        print(f"      2. Tenant não está ativo")
        print(f"      3. Usuário não está ativo")
        print(f"      4. Preferência já está sendo processada por outra instância")
    
    # 5. Verificar lock e last_sent
    print("\n5️⃣ VERIFICANDO LOCK E LAST_SENT_DATE...")
    with transaction.atomic():
        locked_pref_id = UserNotificationPreferences.objects.select_for_update(skip_locked=True).filter(
            id=pref.id,
            last_daily_summary_sent_date__lt=current_date
        ).values_list('id', flat=True).first()
    
    if locked_pref_id:
        print(f"   ✅ Preferência poderia ser processada (lock disponível e não enviado hoje)")
    else:
        print(f"   ❌ Preferência NÃO poderia ser processada")
        if last_sent == current_date:
            print(f"      Motivo: Já foi enviado hoje ({last_sent})")
        else:
            print(f"      Motivo: Lock não disponível (outra instância processando?)")
    
    # 6. Verificar canais habilitados
    print("\n6️⃣ VERIFICANDO CANAIS HABILITADOS...")
    has_whatsapp, has_websocket, has_email, has_any = check_channels_enabled(pref, user)
    print(f"   - WhatsApp: {'✅' if has_whatsapp else '❌'}")
    print(f"   - WebSocket: {'✅' if has_websocket else '❌'}")
    print(f"   - Email: {'✅' if has_email else '❌'}")
    print(f"   - Algum canal: {'✅' if has_any else '❌'}")
    
    if not has_any:
        print(f"   ⚠️ PROBLEMA: Nenhum canal habilitado!")
    
    # 7. Verificar tarefas
    print("\n7️⃣ VERIFICANDO TAREFAS...")
    tasks = Task.objects.filter(
        assigned_to=user,
        tenant=user.tenant,
        task_type='task',
        include_in_notifications=True
    ).exclude(status__in=['cancelled'])
    
    tasks_today = tasks.filter(due_date__date=current_date)
    pending_no_date = tasks.filter(
        due_date__isnull=True,
        status__in=['pending', 'in_progress']
    )
    overdue = tasks.filter(
        due_date__lt=local_now,
        status__in=['pending', 'in_progress']
    )
    
    total = tasks_today.count() + pending_no_date.count() + overdue.count()
    
    print(f"   - Tarefas para hoje: {tasks_today.count()}")
    print(f"   - Pendências sem data: {pending_no_date.count()}")
    print(f"   - Atrasadas: {overdue.count()}")
    print(f"   - Total: {total}")
    
    if total == 0:
        print(f"   ⚠️ PROBLEMA: Nenhuma tarefa encontrada!")
        print(f"      O sistema não envia notificação se não houver tarefas.")
    
    # 8. Resumo e recomendações
    print("\n" + "=" * 80)
    print("📊 RESUMO DO DIAGNÓSTICO")
    print("=" * 80)
    
    issues = []
    
    if not in_window:
        issues.append("❌ Horário agendado não está na janela atual")
    
    if last_sent == current_date:
        issues.append("❌ Já foi marcado como enviado hoje")
    
    if pref.id not in preference_ids:
        issues.append("❌ Preferência não seria encontrada pelo scheduler")
    
    if not has_any:
        issues.append("❌ Nenhum canal habilitado")
    
    if total == 0:
        issues.append("❌ Nenhuma tarefa encontrada")
    
    if not user.tenant.status == 'active':
        issues.append("❌ Tenant não está ativo")
    
    if not user.is_active:
        issues.append("❌ Usuário não está ativo")
    
    if issues:
        print("\n⚠️ PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ Tudo parece estar OK!")
        print("   Se a notificação não chegou, pode ser:")
        print("   1. Scheduler não está rodando")
        print("   2. Erro silencioso no envio (verificar logs do Django)")
        print("   3. Problema de conexão com Evolution API")
    
    print("\n💡 RECOMENDAÇÕES:")
    print("   1. Verificar se o scheduler está rodando (logs do Django)")
    print("   2. Verificar logs com prefixo [DAILY NOTIFICATIONS]")
    print("   3. Verificar logs com prefixo [WHATSAPP NOTIFICATION]")
    print("   4. Se necessário, resetar last_daily_summary_sent_date para testar:")
    print(f"      UserNotificationPreferences.objects.filter(id={pref.id}).update(last_daily_summary_sent_date=None)")
    print("\n")

if __name__ == '__main__':
    diagnose_notification_issue()

