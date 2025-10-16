"""
Comando para iniciar o RabbitMQ Consumer
"""
from django.core.management.base import BaseCommand
import time
import logging

from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Inicia o RabbitMQ Consumer para processamento de campanhas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-start',
            action='store_true',
            help='Inicia automaticamente campanhas pendentes',
        )

    def handle(self, *args, **options):
        auto_start = options['auto_start']
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Iniciando RabbitMQ Consumer...')
        )
        
        try:
            # Iniciar consumer
            consumer = get_rabbitmq_consumer()
            if not consumer:
                self.stdout.write(
                    self.style.ERROR('❌ RabbitMQ não está configurado!')
                )
                return
                
            # Consumer com aio-pika não precisa de start() - é lazy connection
            
            if auto_start:
                self.stdout.write('🔄 Iniciando campanhas pendentes...')
                self._start_pending_campaigns()
            
            self.stdout.write(
                self.style.SUCCESS('✅ RabbitMQ Consumer (aio-pika) iniciado com sucesso!')
            )
            self.stdout.write('📊 Consumer está rodando. Pressione Ctrl+C para parar.')
            
            # Loop principal
            while True:
                try:
                    # Verificar campanhas ativas
                    active_campaigns = list(consumer.consumer_threads.keys())
                    
                    if active_campaigns:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'📊 {len(active_campaigns)} campanhas ativas: {", ".join(active_campaigns[:3])}'
                                + ('...' if len(active_campaigns) > 3 else '')
                            )
                        )
                    else:
                        self.stdout.write('💤 Nenhuma campanha ativa')
                    
                    # Aguardar 30 segundos
                    time.sleep(30)
                    
                except KeyboardInterrupt:
                    self.stdout.write(
                        self.style.WARNING('\n⏹️ Consumer interrompido pelo usuário')
                    )
                    break
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Erro no loop principal: {e}')
                    )
                    time.sleep(10)
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao iniciar consumer: {e}')
            )
            raise
        finally:
            # Parar consumer
            consumer = get_rabbitmq_consumer()
            if consumer:
                # Consumer aio-pika não precisa de stop() - threads são daemon
                pass
            self.stdout.write(
                self.style.SUCCESS('🛑 RabbitMQ Consumer parado')
            )

    def _start_pending_campaigns(self):
        """Inicia campanhas que deveriam estar rodando"""
        from apps.campaigns.models import Campaign
        
        try:
            # Campanhas que deveriam estar rodando mas não estão
            running_campaigns = Campaign.objects.filter(status='running')
            
            for campaign in running_campaigns:
                campaign_id = str(campaign.id)
                
                # Verificar se consumer está ativo
                consumer = get_rabbitmq_consumer()
                if consumer and campaign_id not in consumer.get_active_campaigns():
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ Campanha {campaign.name} deveria estar rodando mas consumer não está ativo'
                        )
                    )
                    
                    # Tentar iniciar
                    try:
                        success = consumer.start_campaign(campaign_id)
                        if success:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ Consumer iniciado para campanha {campaign.name}'
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'❌ Erro ao iniciar consumer para campanha {campaign.name}'
                                )
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ Erro ao iniciar campanha {campaign.name}: {e}'
                            )
                        )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Verificação de campanhas pendentes concluída'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao verificar campanhas pendentes: {e}')
            )
