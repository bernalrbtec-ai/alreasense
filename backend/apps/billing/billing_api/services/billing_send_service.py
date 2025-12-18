"""
BillingSendService - Serviço para envio de mensagens de billing
"""
from django.db import transaction
from django.utils import timezone
from typing import Tuple, Optional
from apps.billing.billing_api import BillingContact, BillingCampaign
from apps.common.services.evolution_api_service import EvolutionAPIService
from apps.notifications.models import WhatsAppInstance
from apps.chat.models import Conversation, Message
from apps.contacts.models import Contact
import logging

logger = logging.getLogger(__name__)


class BillingSendService:
    """
    Serviço para envio de mensagens de billing
    
    Responsabilidades:
    - Enviar mensagem via EvolutionAPIService
    - Salvar no histórico do chat
    - Criar/atualizar Conversation
    - Fechar conversa automaticamente
    """
    
    def __init__(self, billing_contact: BillingContact, instance: WhatsAppInstance):
        self.billing_contact = billing_contact
        self.instance = instance
        self.evolution_service = EvolutionAPIService(instance)
    
    @transaction.atomic
    def send_billing_message(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Envia mensagem de billing
        
        Returns:
            (sucesso, message_id, erro)
        """
        try:
            billing_contact = self.billing_contact
            
            # 1. Validações
            if billing_contact.status != 'pending' and billing_contact.status != 'pending_retry':
                logger.warning(f"BillingContact {billing_contact.id} não está pendente: {billing_contact.status}")
                return False, None, f"Status inválido: {billing_contact.status}"
            
            # 2. Busca telefone do contato
            # Para mensagens de ciclo, pode não ter campaign_contact
            contact = None
            if billing_contact.campaign_contact and billing_contact.campaign_contact.contact:
                contact = billing_contact.campaign_contact.contact
                phone = contact.phone
            elif billing_contact.billing_cycle and billing_contact.billing_cycle.contact:
                contact = billing_contact.billing_cycle.contact
                phone = contact.phone
            elif billing_contact.billing_cycle:
                phone = billing_contact.billing_cycle.contact_phone
                # Mensagem de ciclo sem contato linkado (não ideal, mas funciona)
                contact = None
            else:
                logger.error(f"BillingContact {billing_contact.id} sem contato válido")
                return False, None, "BillingContact sem contato válido"
            
            if not phone:
                logger.error(f"Telefone vazio para BillingContact {billing_contact.id}")
                return False, None, "Contato sem telefone"
            
            # 3. Envia via EvolutionAPIService (síncrono)
            success, response = self.evolution_service.send_text_message(
                phone=phone,
                message=billing_contact.rendered_message,
                max_retries=3
            )
            
            if not success:
                error_msg = response.get('error', 'Erro desconhecido')
                logger.error(f"Falha ao enviar mensagem: {error_msg}")
                
                # Atualiza status
                billing_contact.status = 'failed'
                billing_contact.save(update_fields=['status'])
                
                return False, None, error_msg
            
            # 4. Extrai message_id
            message_id = response.get('key', {}).get('id')
            
            # 5. Salva no chat
            conversation, message = self._save_to_chat(
                contact,
                phone,
                message_id
            )
            
            # 6. Atualiza BillingContact
            billing_contact.status = 'sent'
            billing_contact.sent_at = timezone.now()
            billing_contact.save(update_fields=['status', 'sent_at'])
            
            # 7. Atualiza CampaignContact se existir (mensagens de campanha)
            # Mensagens de ciclo não têm CampaignContact
            campaign_contact = billing_contact.campaign_contact if billing_contact.campaign_contact else None
            if campaign_contact:
                # Atualiza CampaignContact se existir (mensagens de campanha)
                # Mensagens de ciclo não têm CampaignContact
                if campaign_contact:
                    campaign_contact.status = 'sent'
                    campaign_contact.sent_at = timezone.now()
                    campaign_contact.whatsapp_message_id = message_id
                campaign_contact.save(update_fields=['status', 'sent_at', 'whatsapp_message_id'])
            
            # 8. Fecha conversa automaticamente
            if conversation:
                conversation.status = 'closed'
                conversation.closed_at = timezone.now()
                conversation.save(update_fields=['status', 'closed_at'])
            
            logger.info(
                f"✅ Mensagem de billing enviada: {billing_contact.id} "
                f"(message_id: {message_id})"
            )
            
            return True, message_id, None
        
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de billing: {e}", exc_info=True)
            return False, None, str(e)
    
    def _save_to_chat(
        self,
        contact: Contact,
        phone: str,
        whatsapp_message_id: str
    ) -> Tuple[Optional[Conversation], Optional[Message]]:
        """
        Salva mensagem no histórico do chat
        
        Returns:
            (conversation, message)
        """
        try:
            billing_contact = self.billing_contact
            
            # Busca ou cria Conversation
            conversation, _ = Conversation.objects.get_or_create(
                tenant=billing_contact.billing_campaign.tenant,
                contact_phone=phone,
                defaults={
                    'contact_name': contact.name,
                    'instance_name': self.instance.instance_name,
                    'status': 'open',
                    'conversation_type': 'individual'
                }
            )
            
            # Cria Message
            message = Message.objects.create(
                conversation=conversation,
                content=billing_contact.rendered_message,
                direction='outgoing',
                status='sent',
                whatsapp_message_id=whatsapp_message_id,
                metadata={
                    'is_billing_message': True,
                    'billing_contact_id': str(billing_contact.id),
                    'billing_campaign_id': str(billing_contact.billing_campaign.id),
                    'template_type': billing_contact.billing_campaign.billing_type
                }
            )
            
            logger.debug(f"Mensagem salva no chat: {message.id}")
            return conversation, message
        
        except Exception as e:
            logger.error(f"Erro ao salvar no chat: {e}", exc_info=True)
            return None, None



