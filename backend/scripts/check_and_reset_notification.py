#!/usr/bin/env python
"""
Script para verificar e resetar last_daily_summary_sent_date.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences
from django.utils import timezone

def check_and_reset():
    """Verifica e reseta last_daily_summary_sent_date"""
    
    print("=" * 80)
    print("🔍 VERIFICANDO E RESETANDO NOTIFICAÇÃO")
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
    current_date = timezone.localtime(timezone.now()).date()
    
    print(f"\n👤 Usuário: {user.email}")
    print(f"   - ID da preferência: {pref.id}")
    print(f"   - Horário agendado: {pref.daily_summary_time}")
    print(f"   - Último envio ANTES: {pref.last_daily_summary_sent_date}")
    print(f"   - Data atual: {current_date}")
    
    # Verificar se está marcado como enviado hoje
    if pref.last_daily_summary_sent_date == current_date:
        print(f"\n⚠️ PROBLEMA: Está marcado como enviado hoje ({pref.last_daily_summary_sent_date})")
        print(f"   Isso impede que o scheduler envie novamente.")
        
        # Resetar
        print(f"\n🔄 Resetando last_daily_summary_sent_date...")
        pref.last_daily_summary_sent_date = None
        pref.save(update_fields=['last_daily_summary_sent_date'])
        
        # Verificar novamente
        pref.refresh_from_db()
        print(f"   ✅ Último envio DEPOIS: {pref.last_daily_summary_sent_date}")
        
        if pref.last_daily_summary_sent_date is None:
            print(f"\n✅ Reset realizado com sucesso!")
            print(f"   O scheduler pode tentar enviar novamente agora.")
        else:
            print(f"\n❌ ERRO: Não foi possível resetar!")
    else:
        print(f"\n✅ Status OK: Não está marcado como enviado hoje")
        print(f"   Último envio: {pref.last_daily_summary_sent_date if pref.last_daily_summary_sent_date else 'Nunca'}")
    
    # Mostrar SQL direto também
    print("\n" + "=" * 80)
    print("📝 SQL PARA EXECUTAR DIRETAMENTE NO BANCO:")
    print("=" * 80)
    print(f"""
UPDATE notifications_user_notification_preferences
SET last_daily_summary_sent_date = NULL
WHERE id = '{pref.id}';

-- Verificar resultado
SELECT 
    id,
    daily_summary_enabled,
    daily_summary_time,
    last_daily_summary_sent_date
FROM notifications_user_notification_preferences
WHERE id = '{pref.id}';
""")
    
    print("\n" + "=" * 80)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("=" * 80)

if __name__ == '__main__':
    check_and_reset()

