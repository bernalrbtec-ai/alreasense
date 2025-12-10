#!/usr/bin/env python
"""
Script simples para resetar last_daily_summary_sent_date.
Permite que o scheduler tente enviar novamente.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences

def reset_notification_flag():
    """Reseta last_daily_summary_sent_date para permitir novo envio"""
    
    print("=" * 80)
    print("🔄 RESETANDO FLAG DE NOTIFICAÇÃO")
    print("=" * 80)
    
    # Buscar preferência
    pref = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user').first()
    
    if not pref:
        print("❌ Nenhuma preferência encontrada!")
        return
    
    user = pref.user
    print(f"\n👤 Usuário: {user.email}")
    print(f"   - Horário agendado: {pref.daily_summary_time.strftime('%H:%M:%S')}")
    print(f"   - Último envio ANTES: {pref.last_daily_summary_sent_date}")
    
    # Resetar
    print("\n🔄 Resetando last_daily_summary_sent_date...")
    pref.last_daily_summary_sent_date = None
    pref.save(update_fields=['last_daily_summary_sent_date'])
    
    print("✅ Resetado com sucesso!")
    print(f"   - Último envio DEPOIS: {pref.last_daily_summary_sent_date}")
    
    print("\n" + "=" * 80)
    print("✅ RESET CONCLUÍDO")
    print("=" * 80)
    print("\n💡 Agora o scheduler pode tentar enviar novamente.")
    print("   O scheduler verifica a cada 60 segundos.")
    print("   Se o horário agendado estiver na janela (±1 minuto), será enviado.")
    print("\n   Para forçar envio agora, execute:")
    print("   python backend/scripts/force_send_notifications.py")
    print("\n")

if __name__ == '__main__':
    reset_notification_flag()

