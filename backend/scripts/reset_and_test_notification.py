#!/usr/bin/env python
"""
Script para resetar last_daily_summary_sent_date e testar envio manualmente.
"""
import os
import sys
import django
from django.utils import timezone

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.notifications.models import UserNotificationPreferences
from apps.campaigns.apps import CampaignsConfig
import logging

logger = logging.getLogger(__name__)

def reset_and_test():
    """Reseta last_daily_summary_sent_date e testa envio"""
    
    print("=" * 80)
    print("🔄 RESETANDO E TESTANDO NOTIFICAÇÃO")
    print("=" * 80)
    
    # Buscar preferência
    pref = UserNotificationPreferences.objects.filter(
        daily_summary_enabled=True,
        daily_summary_time__isnull=False
    ).select_related('user', 'tenant').first()
    
    if not pref:
        print("❌ Nenhuma preferência encontrada!")
        return
    
    user = pref.user
    print(f"\n👤 Usuário: {user.email}")
    print(f"   - Horário agendado: {pref.daily_summary_time.strftime('%H:%M:%S')}")
    print(f"   - Último envio ANTES do reset: {pref.last_daily_summary_sent_date}")
    
    # Resetar
    print("\n🔄 Resetando last_daily_summary_sent_date...")
    pref.last_daily_summary_sent_date = None
    pref.save(update_fields=['last_daily_summary_sent_date'])
    print("✅ Resetado com sucesso!")
    
    # Testar envio manual usando check_user_daily_summaries
    print("\n📤 Testando envio manual...")
    local_now = timezone.localtime(timezone.now())
    current_time = local_now.time()
    current_date = local_now.date()
    
    # Chamar função do scheduler diretamente
    try:
        # Importar e chamar função de verificação do scheduler
        # Ela vai encontrar a preferência e enviar
        from apps.campaigns.apps import CampaignsConfig
        
        # Criar instância temporária para acessar métodos
        config = CampaignsConfig('campaigns', None)
        
        # Chamar função de verificação (ela vai encontrar e enviar)
        print("   Chamando check_user_daily_summaries...")
        print(f"   Horário atual: {current_time.strftime('%H:%M:%S')}")
        print(f"   Janela será calculada automaticamente...")
        
        # Ajustar horário agendado temporariamente para estar na janela atual
        # (apenas para teste)
        time_window_start, time_window_end = calculate_time_window(current_time, window_minutes=1)
        print(f"   Janela atual: {time_window_start.strftime('%H:%M:%S')} - {time_window_end.strftime('%H:%M:%S')}")
        
        # Temporariamente ajustar horário para estar na janela
        original_time = pref.daily_summary_time
        # Ajustar para o meio da janela atual
        import datetime
        mid_window = datetime.datetime.combine(datetime.date.today(), time_window_start) + datetime.timedelta(seconds=30)
        pref.daily_summary_time = mid_window.time()
        pref.save(update_fields=['daily_summary_time'])
        print(f"   ⚠️ Horário temporariamente ajustado para: {pref.daily_summary_time.strftime('%H:%M:%S')} (para teste)")
        
        # Chamar verificação
        config.check_user_daily_summaries(current_time, current_date)
        
        # Restaurar horário original
        pref.daily_summary_time = original_time
        pref.save(update_fields=['daily_summary_time'])
        print(f"   ✅ Horário restaurado para: {original_time.strftime('%H:%M:%S')}")
        
        print("✅ Verificação concluída!")
        
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        import traceback
        traceback.print_exc()
        
        # Restaurar horário em caso de erro
        if 'original_time' in locals():
            pref.daily_summary_time = original_time
            pref.save(update_fields=['daily_summary_time'])
    
    # Verificar resultado
    pref.refresh_from_db()
    print(f"\n📊 Resultado:")
    print(f"   - Último envio APÓS teste: {pref.last_daily_summary_sent_date}")
    
    if pref.last_daily_summary_sent_date == current_date:
        print("✅ Notificação foi processada e marcada como enviada!")
    else:
        print("⚠️ Notificação não foi marcada como enviada (pode ter falhado)")
    
    print("\n" + "=" * 80)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 80)
    print("\n💡 Verifique o WhatsApp para confirmar se a mensagem chegou!")
    print("   Se não chegou, verifique os logs do Django para ver o erro.")

if __name__ == '__main__':
    reset_and_test()

