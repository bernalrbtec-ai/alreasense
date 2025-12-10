#!/usr/bin/env python
"""
Script para testar o fluxo completo de envio de notificação WhatsApp.
Simula o que o scheduler faz quando chega o horário agendado.
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
from apps.notifications.services import send_whatsapp_notification, normalize_phone, _get_whatsapp_config
from apps.contacts.models import Task
import logging

logger = logging.getLogger(__name__)

def test_notification_flow():
    """Testa o fluxo completo de envio de notificação"""
    
    print("=" * 80)
    print("🧪 TESTE DO FLUXO DE NOTIFICAÇÃO WHATSAPP")
    print("=" * 80)
    
    # Buscar preferência de teste
    pref = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user', 'tenant').first()
    
    if not pref:
        print("❌ Nenhuma preferência de notificação encontrada!")
        return
    
    user = pref.user
    print(f"\n👤 Usuário de teste: {user.email}")
    print(f"   - Horário agendado: {pref.daily_summary_time.strftime('%H:%M')}")
    print(f"   - Telefone: {user.phone}")
    
    # 1. Verificar telefone
    if not user.phone:
        print("❌ Usuário não tem telefone cadastrado!")
        return
    
    phone_normalized = normalize_phone(user.phone)
    if not phone_normalized:
        print(f"❌ Telefone inválido: {user.phone}")
        return
    
    print(f"   ✅ Telefone normalizado: {phone_normalized}")
    
    # 2. Verificar configuração WhatsApp
    base_url, api_key, instance_name = _get_whatsapp_config(user)
    
    if not base_url or not api_key:
        print("❌ Configuração WhatsApp não encontrada!")
        print(f"   - Base URL: {base_url}")
        print(f"   - API Key: {'✅' if api_key else '❌'}")
        print(f"   - Instance: {instance_name}")
        return
    
    print(f"   ✅ Configuração WhatsApp OK")
    print(f"      - URL: {base_url}")
    print(f"      - Instance: {instance_name}")
    
    # 3. Verificar tarefas
    local_now = timezone.localtime(timezone.now())
    current_date = local_now.date()
    
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
    
    print(f"\n📋 Tarefas encontradas:")
    print(f"   - Para hoje: {tasks_today.count()}")
    print(f"   - Pendências sem data: {pending_no_date.count()}")
    print(f"   - Atrasadas: {overdue.count()}")
    
    total = tasks_today.count() + pending_no_date.count() + overdue.count()
    
    if total == 0:
        print("\n⚠️ Nenhuma tarefa encontrada para notificar!")
        print("   Criando tarefa de teste...")
        
        # Criar tarefa de teste
        from apps.contacts.models import Task
        test_task = Task.objects.create(
            title="Tarefa de teste - Verificação de notificações",
            description="Esta é uma tarefa de teste para verificar o sistema de notificações",
            assigned_to=user,
            tenant=user.tenant,
            task_type='task',
            status='pending',
            priority='medium',
            include_in_notifications=True
        )
        print(f"   ✅ Tarefa de teste criada: {test_task.title}")
        total = 1
    
    # 4. Preparar mensagem de teste
    message = f"""🧪 *TESTE DE NOTIFICAÇÃO*

Este é um teste do sistema de notificações WhatsApp.

👤 Usuário: {user.email}
📱 Telefone: {phone_normalized}
📅 Data: {current_date.strftime('%d/%m/%Y')}
⏰ Horário: {local_now.strftime('%H:%M:%S')}

✅ Sistema funcionando corretamente!

📋 Total de tarefas: {total}
"""
    
    print(f"\n📱 Mensagem de teste preparada:")
    print("   " + "\n   ".join(message.split("\n")))
    
    # 5. Perguntar se deve enviar
    print("\n" + "=" * 80)
    resposta = input("Deseja enviar a mensagem de teste? (s/n): ").strip().lower()
    
    if resposta == 's':
        print("\n📤 Enviando mensagem...")
        try:
            success = send_whatsapp_notification(user, message)
            if success:
                print("✅ Mensagem enviada com sucesso!")
            else:
                print("❌ Falha ao enviar mensagem")
        except Exception as e:
            print(f"❌ Erro ao enviar: {e}")
            logger.error(f"Erro ao enviar teste: {e}", exc_info=True)
    else:
        print("⏭️ Envio cancelado pelo usuário")
    
    print("\n" + "=" * 80)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 80)

if __name__ == '__main__':
    test_notification_flow()

