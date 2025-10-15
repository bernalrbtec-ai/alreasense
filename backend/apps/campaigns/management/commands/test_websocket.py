"""
Comando Django para testar WebSocket de campanhas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.campaigns.models import Campaign
from apps.campaigns.rabbitmq_consumer import RabbitMQConsumer
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Testa envio de updates WebSocket para campanhas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            type=str,
            help='ID da campanha para testar',
            required=True
        )

    def handle(self, *args, **options):
        campaign_id = options['campaign_id']
        
        try:
            # Buscar campanha
            campaign = Campaign.objects.get(id=campaign_id)
            self.stdout.write(f"📋 Campanha encontrada: {campaign.name}")
            
            # Criar instância do consumer
            consumer = RabbitMQConsumer()
            
            # Simular diferentes tipos de eventos
            events_to_test = [
                {
                    'event_type': 'campaign_started',
                    'extra_data': {
                        'event': 'campaign_started',
                        'total_contacts': campaign.total_contacts,
                        'pending_contacts': campaign.total_contacts - campaign.messages_sent
                    }
                },
                {
                    'event_type': 'message_sent',
                    'extra_data': {
                        'event': 'message_sent',
                        'contact_name': 'João Teste',
                        'contact_phone': '11999999999'
                    }
                },
                {
                    'event_type': 'next_message_starting',
                    'extra_data': {
                        'event': 'next_message_starting',
                        'contact_name': 'Maria Teste',
                        'contact_phone': '11888888888'
                    }
                }
            ]
            
            for event in events_to_test:
                self.stdout.write(f"🔧 Enviando evento: {event['event_type']}")
                consumer._send_websocket_update(campaign, event['event_type'], event['extra_data'])
                self.stdout.write(f"✅ Evento {event['event_type']} enviado")
                
                # Pequena pausa entre eventos
                import time
                time.sleep(2)
            
            self.stdout.write(
                self.style.SUCCESS('🎉 Teste WebSocket concluído com sucesso!')
            )
            
        except Campaign.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Campanha com ID {campaign_id} não encontrada')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro durante o teste: {str(e)}')
            )
