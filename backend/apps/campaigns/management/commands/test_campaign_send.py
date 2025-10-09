from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.campaigns.models import Campaign, CampaignMessage, CampaignContact
from apps.contacts.models import Contact
from apps.notifications.models import WhatsAppInstance
from apps.tenancy.models import Tenant
from apps.authn.models import User


class Command(BaseCommand):
    help = 'Cria campanha de teste e envia mensagem para 5517991253112'
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Criando campanha de teste...')
        
        try:
            # Pegar tenant e usuário
            tenant = Tenant.objects.first()
            user = User.objects.filter(is_superuser=True).first()
            
            if not tenant or not user:
                self.stdout.write(self.style.ERROR('❌ Tenant ou usuário não encontrado'))
                return
            
            # Pegar instância conectada
            instance = WhatsAppInstance.objects.filter(
                tenant=tenant,
                connection_state='open'
            ).first()
            
            if not instance:
                self.stdout.write(self.style.ERROR('❌ Nenhuma instância WhatsApp conectada encontrada'))
                return
            
            self.stdout.write(f'✓ Usando instância: {instance.friendly_name}')
            
            # Criar ou pegar contato
            contact, _ = Contact.objects.get_or_create(
                tenant=tenant,
                phone='+5517991253112',
                defaults={
                    'name': 'Paulo (Teste ALREA)',
                    'quem_indicou': 'Sistema ALREA',
                    'is_active': True
                }
            )
            self.stdout.write(f'✓ Contato: {contact.name}')
            
            # Criar campanha
            campaign = Campaign.objects.create(
                tenant=tenant,
                name='🎉 TESTE ALREA Campaigns - Sistema Funcionando!',
                description='Campanha de teste automático do sistema ALREA Campaigns',
                instance=instance,
                status=Campaign.Status.DRAFT,
                schedule_type=Campaign.ScheduleType.IMMEDIATE,
                created_by=user
            )
            self.stdout.write(f'✓ Campanha criada: {campaign.name}')
            
            # Criar mensagem
            message = CampaignMessage.objects.create(
                campaign=campaign,
                message_text='''{{saudacao}}, {{nome}}! 🎉

✅ *ALREA Campaigns está FUNCIONANDO!*

O sistema de campanhas foi implementado com sucesso e está operacional!

*Funcionalidades Implementadas:*
📤 Sistema completo de campanhas
👥 Gestão de contatos
⏰ Agendamento inteligente (horários/feriados)
🔄 Rotação automática de mensagens
📊 Métricas e logs detalhados
🤖 Celery Beat para processamento automático

Esta é uma mensagem de teste enviada automaticamente pelo sistema.

Desenvolvido com ❤️ pela equipe ALREA''',
                order=1,
                is_active=True
            )
            self.stdout.write('✓ Mensagem criada')
            
            # Adicionar contato à campanha
            campaign_contact = CampaignContact.objects.create(
                campaign=campaign,
                contact=contact,
                status=CampaignContact.Status.PENDING
            )
            
            campaign.total_contacts = 1
            campaign.save()
            
            self.stdout.write('✓ Contato adicionado à campanha')
            
            # Iniciar campanha
            campaign.start(user=user)
            self.stdout.write(self.style.SUCCESS('✅ Campanha INICIADA!'))
            
            self.stdout.write(self.style.SUCCESS('''
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 CAMPANHA DE TESTE CRIADA E INICIADA!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 Destinatário: Paulo (+5517991253112)
⚡ Status: ACTIVE
🚀 Envio: Será processado nos próximos 10 segundos

O Celery Beat scheduler irá processar automaticamente.
Você receberá a mensagem em breve!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {str(e)}'))
            import traceback
            traceback.print_exc()

