"""
Comando para iniciar o engine de campanhas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import logging

from apps.campaigns.engine import campaign_manager
from apps.campaigns.monitor import system_health_monitor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Inicia o engine de campanhas com monitoramento'

    def add_arguments(self, parser):
        parser.add_argument(
            '--monitor-only',
            action='store_true',
            help='Apenas monitora campanhas existentes',
        )
        parser.add_argument(
            '--health-interval',
            type=int,
            default=30,
            help='Intervalo de health check em segundos (padrão: 30)',
        )

    def handle(self, *args, **options):
        monitor_only = options['monitor_only']
        health_interval = options['health_interval']
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Iniciando Engine de Campanhas...')
        )
        
        try:
            if monitor_only:
                self.stdout.write('🔍 Modo monitoramento ativo')
                self._run_monitoring(health_interval)
            else:
                self.stdout.write('🎯 Modo completo ativo')
                self._run_full_engine(health_interval)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\n⏹️ Engine interrompido pelo usuário')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro no engine: {e}')
            )
            raise

    def _run_full_engine(self, health_interval):
        """Executa engine completo"""
        self.stdout.write('🎯 Iniciando engine completo...')
        
        # Loop principal
        while True:
            try:
                # Verificar campanhas que precisam ser iniciadas
                self._check_pending_campaigns()
                
                # Monitorar saúde
                self._monitor_health()
                
                # Aguardar próximo ciclo
                time.sleep(health_interval)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Erro no loop principal: {e}')
                )
                time.sleep(10)  # Pausa em caso de erro

    def _run_monitoring(self, health_interval):
        """Executa apenas monitoramento"""
        self.stdout.write('🔍 Iniciando monitoramento...')
        
        while True:
            try:
                self._monitor_health()
                time.sleep(health_interval)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Erro no monitoramento: {e}')
                )
                time.sleep(10)

    def _check_pending_campaigns(self):
        """Verifica campanhas pendentes"""
        from apps.campaigns.models import Campaign
        
        # Campanhas que deveriam estar rodando mas não estão
        running_campaigns = Campaign.objects.filter(status='running')
        
        for campaign in running_campaigns:
            campaign_id = str(campaign.id)
            
            # Verificar se engine está ativo
            if campaign_id not in campaign_manager.list_active_campaigns():
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️ Campanha {campaign.name} deveria estar rodando mas engine não está ativo'
                    )
                )
                
                # Tentar reiniciar
                try:
                    campaign_manager.start_campaign(campaign_id)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Engine reiniciado para campanha {campaign.name}'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Erro ao reiniciar campanha {campaign.name}: {e}'
                        )
                    )

    def _monitor_health(self):
        """Monitora saúde do sistema"""
        try:
            # Health check do sistema
            system_health_monitor.monitor_all_campaigns()
            
            # Status das campanhas ativas
            active_campaigns = campaign_manager.list_active_campaigns()
            
            if active_campaigns:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'📊 {len(active_campaigns)} campanhas ativas: {", ".join(active_campaigns[:3])}'
                        + ('...' if len(active_campaigns) > 3 else '')
                    )
                )
            else:
                self.stdout.write('💤 Nenhuma campanha ativa')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro no health check: {e}')
            )
