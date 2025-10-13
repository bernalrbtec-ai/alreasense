#!/usr/bin/env python
"""
Script para configurar notificações no Railway
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

def setup_railway_notifications():
    """Configura notificações no Railway"""
    print("🚀 Configurando notificações no Railway...")
    
    # Importar e executar criação de templates
    from create_notification_templates import create_whatsapp_templates
    
    try:
        # Criar templates
        create_whatsapp_templates()
        
        print("\n✅ Configuração concluída!")
        print("\n📱 Templates criados:")
        print("   • celery_worker_down - Workers param")
        print("   • celery_worker_up - Workers voltam")
        print("   • campaign_started - Campanha inicia")
        print("   • campaign_paused - Campanha pausa")
        print("   • campaign_resumed - Campanha retoma")
        print("   • campaign_completed - Campanha termina")
        print("   • campaign_cancelled - Campanha cancela")
        print("   • whatsapp_instance_down - Instância desconecta")
        print("   • whatsapp_instance_up - Instância conecta")
        
        print("\n🔧 Como usar:")
        print("   1. Configure uma instância WhatsApp em Admin → Notifications → WhatsApp Instances")
        print("   2. Execute: python send_system_notifications.py worker_down")
        print("   3. Execute: python monitor_and_notify.py --continuous 60")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na configuração: {e}")
        return False

if __name__ == "__main__":
    setup_railway_notifications()
