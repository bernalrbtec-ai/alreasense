"""
Comando Django para testar substituição de variáveis em mensagens
"""
from django.core.management.base import BaseCommand
from apps.campaigns.models import Campaign
from apps.campaigns.rabbitmq_consumer import RabbitMQConsumer

class Command(BaseCommand):
    help = 'Testa substituição de variáveis em mensagens de campanhas'

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
            
            # Criar um contato mock para teste
            class MockContact:
                def __init__(self):
                    self.name = "João Silva"
                    self.phone = "11999999999"
                    self.referred_by = "Maria Santos"
            
            mock_contact = MockContact()
            
            # Mensagens de teste com variáveis essenciais
            test_messages = [
                "{{saudacao}} {{nome}}, como você está?",
                "Oi {{primeiro_nome}}! Foi indicado pela {{quem_indicou}}",
                "Bem-vindo {{nome}}! Hoje é {{dia_semana}}",
                "Olá {{primeiro_nome}}, {{primeiro_nome_indicador}} me indicou você",
                "{{saudacao}} {{nome}}! Que {{dia_semana}} linda!",
                "Oi {{primeiro_nome}}, {{quem_indicou}} falou muito bem de você"
            ]
            
            self.stdout.write(f"\n🧪 Testando substituição de variáveis essenciais:")
            self.stdout.write(f"📝 Contato de teste: {mock_contact.name}")
            self.stdout.write(f"👥 Indicado por: {mock_contact.referred_by}")
            
            for i, message in enumerate(test_messages, 1):
                self.stdout.write(f"\n--- Teste {i} ---")
                self.stdout.write(f"📥 Original: {message}")
                
                processed = consumer._replace_message_variables(message, mock_contact)
                
                self.stdout.write(f"📤 Processado: {processed}")
                
                if message != processed:
                    self.stdout.write(f"✅ Variáveis substituídas com sucesso!")
                else:
                    self.stdout.write(f"ℹ️ Nenhuma variável encontrada")
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Teste de variáveis concluído com sucesso!')
            )
            
        except Campaign.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Campanha com ID {campaign_id} não encontrada')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro durante o teste: {str(e)}')
            )
