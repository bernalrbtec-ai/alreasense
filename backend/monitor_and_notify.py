#!/usr/bin/env python
"""
Script para monitorar workers e campanhas e enviar notificações automáticas
"""
import os
import sys
import django
import time
from datetime import datetime, timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.utils import timezone
from apps.campaigns.models import Campaign
from apps.notifications.models import WhatsAppInstance
from send_system_notifications import (
    send_celery_worker_down_notification,
    send_celery_worker_up_notification,
    send_campaign_notification,
    send_whatsapp_instance_notification
)

class SystemMonitor:
    """Monitor do sistema para detectar mudanças e enviar notificações"""
    
    def __init__(self):
        self.last_worker_check = None
        self.workers_online = True
        self.campaign_states = {}  # {campaign_id: status}
        self.instance_states = {}  # {instance_id: status}
        
    def check_celery_workers(self):
        """Verifica status dos workers do Celery"""
        try:
            from alrea_sense.celery import app
            inspect = app.control.inspect()
            active_workers = inspect.active()
            
            current_status = len(active_workers) > 0 if active_workers else False
            
            # Se status mudou
            if self.last_worker_check is not None and current_status != self.workers_online:
                if current_status:
                    print("✅ Workers voltaram online - enviando notificação")
                    send_celery_worker_up_notification()
                else:
                    print("❌ Workers ficaram offline - enviando notificação")
                    send_celery_worker_down_notification()
            
            self.workers_online = current_status
            self.last_worker_check = timezone.now()
            
            return current_status
            
        except Exception as e:
            print(f"❌ Erro ao verificar workers: {e}")
            return False
    
    def check_campaigns(self):
        """Verifica mudanças de status nas campanhas"""
        try:
            campaigns = Campaign.objects.filter(status__in=['running', 'paused', 'completed', 'cancelled'])
            
            for campaign in campaigns:
                campaign_id = str(campaign.id)
                current_status = campaign.status
                last_status = self.campaign_states.get(campaign_id)
                
                # Se status mudou
                if last_status and last_status != current_status:
                    print(f"📧 Campanha {campaign.name} mudou de {last_status} para {current_status}")
                    
                    # Enviar notificação baseada no novo status
                    if current_status == 'running' and last_status == 'paused':
                        send_campaign_notification(campaign, 'resumed')
                    elif current_status == 'running':
                        send_campaign_notification(campaign, 'started')
                    elif current_status == 'paused':
                        send_campaign_notification(campaign, 'paused')
                    elif current_status == 'completed':
                        send_campaign_notification(campaign, 'completed')
                    elif current_status == 'cancelled':
                        send_campaign_notification(campaign, 'cancelled')
                
                # Atualizar estado
                self.campaign_states[campaign_id] = current_status
                
        except Exception as e:
            print(f"❌ Erro ao verificar campanhas: {e}")
    
    def check_whatsapp_instances(self):
        """Verifica mudanças de status nas instâncias WhatsApp"""
        try:
            instances = WhatsAppInstance.objects.filter(is_active=True)
            
            for instance in instances:
                instance_id = str(instance.id)
                current_status = instance.status
                last_status = self.instance_states.get(instance_id)
                
                # Se status mudou
                if last_status and last_status != current_status:
                    print(f"📱 Instância {instance.friendly_name} mudou de {last_status} para {current_status}")
                    
                    # Enviar notificação baseada no novo status
                    if current_status == 'active' and last_status == 'inactive':
                        send_whatsapp_instance_notification(instance, 'up')
                    elif current_status == 'inactive' and last_status == 'active':
                        send_whatsapp_instance_notification(instance, 'down')
                    elif current_status == 'error':
                        send_whatsapp_instance_notification(instance, 'down')
                
                # Atualizar estado
                self.instance_states[instance_id] = current_status
                
        except Exception as e:
            print(f"❌ Erro ao verificar instâncias WhatsApp: {e}")
    
    def run_monitoring_cycle(self):
        """Executa um ciclo completo de monitoramento"""
        print(f"🔍 Monitorando sistema - {datetime.now().strftime('%H:%M:%S')}")
        
        # Verificar workers
        workers_status = self.check_celery_workers()
        print(f"   🔧 Workers: {'✅ Online' if workers_status else '❌ Offline'}")
        
        # Verificar campanhas
        self.check_campaigns()
        active_campaigns = Campaign.objects.filter(status='running').count()
        print(f"   📧 Campanhas ativas: {active_campaigns}")
        
        # Verificar instâncias WhatsApp
        self.check_whatsapp_instances()
        active_instances = WhatsAppInstance.objects.filter(status='active', is_active=True).count()
        print(f"   📱 Instâncias WhatsApp ativas: {active_instances}")
        
        return True
    
    def run_continuous_monitoring(self, interval=30):
        """Executa monitoramento contínuo"""
        print(f"🚀 Iniciando monitoramento contínuo (intervalo: {interval}s)")
        print("Pressione Ctrl+C para parar\n")
        
        try:
            while True:
                self.run_monitoring_cycle()
                print(f"⏳ Próxima verificação em {interval} segundos...\n")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitoramento interrompido pelo usuário")

def main():
    """Função principal"""
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor = SystemMonitor()
        monitor.run_continuous_monitoring(interval)
    else:
        # Execução única
        monitor = SystemMonitor()
        monitor.run_monitoring_cycle()

if __name__ == "__main__":
    main()
