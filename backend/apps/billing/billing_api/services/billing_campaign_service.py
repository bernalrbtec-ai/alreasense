"""
BillingCampaignService - Orchestrator de campanhas de billing
"""
from django.db import transaction
from django.utils import timezone
from typing import Dict, List, Any, Tuple, Optional
from apps.billing.billing_api import (
    BillingCampaign, BillingQueue, BillingContact, BillingTemplate, BillingTemplateVariation
)
from apps.billing.billing_api.utils.date_calculator import BillingDateCalculator
from apps.billing.billing_api.utils.template_engine import BillingTemplateEngine
from apps.billing.billing_api.utils.template_sanitizer import TemplateSanitizer
from apps.campaigns.models import Campaign, CampaignContact
from apps.contacts.models import Contact
from apps.contacts.utils import normalize_phone
from apps.tenancy.models import Tenant
import logging
import random

logger = logging.getLogger(__name__)


class BillingCampaignService:
    """
    Serviço orquestrador de campanhas de billing
    
    Responsabilidades:
    - Validar dados recebidos
    - Enriquecer variáveis (calcular dias, etc)
    - Criar Campaign + BillingCampaign
    - Criar contatos
    - Selecionar variações de template
    - Criar BillingQueue
    """
    
    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.config = getattr(tenant, 'billing_config', None)
        self.date_calculator = BillingDateCalculator()
        self.template_engine = BillingTemplateEngine()
    
    @transaction.atomic
    def create_billing_campaign(
        self,
        template_type: str,
        contacts_data: List[Dict[str, Any]],
        external_id: Optional[str] = None,
        instance_id: Optional[str] = None
    ) -> Tuple[bool, Optional[BillingCampaign], str]:
        """
        Cria campanha de billing completa
        
        Args:
            template_type: 'overdue' | 'upcoming' | 'notification'
            contacts_data: Lista de contatos com dados da cobrança
            external_id: ID externo (opcional)
            instance_id: ID da instância WhatsApp (opcional)
        
        Returns:
            (sucesso, billing_campaign, mensagem_erro)
        """
        try:
            # 1. Validações iniciais
            valid, error = self._validate_request(template_type, contacts_data, external_id)
            if not valid:
                return False, None, error
            
            # 2. Busca template
            template = self._get_template(template_type)
            if not template:
                return False, None, f"Template '{template_type}' não encontrado ou inativo"
            
            # 3. Cria Campaign base (reutiliza infraestrutura existente)
            campaign = self._create_base_campaign(template_type, len(contacts_data), instance_id)
            
            # 4. Cria BillingCampaign
            billing_campaign = BillingCampaign.objects.create(
                tenant=self.tenant,
                campaign=campaign,
                template=template,
                external_id=external_id,
                billing_type=template_type
            )
            
            # 5. Cria BillingQueue
            queue = BillingQueue.objects.create(
                billing_campaign=billing_campaign,
                status='pending',
                total_contacts=len(contacts_data)
            )
            
            # 6. Cria contatos (em batch)
            contacts_created = self._create_contacts(
                billing_campaign,
                campaign,
                template,
                contacts_data
            )
            
            # 7. Publica no RabbitMQ para processamento assíncrono
            try:
                from apps.billing.billing_api.rabbitmq.billing_publisher import BillingQueuePublisher
                import asyncio
                
                # Publica a queue no RabbitMQ
                asyncio.run(
                    BillingQueuePublisher.publish_queue(
                        str(queue.id),
                        template_type
                    )
                )
                
                logger.info(f"📤 Queue {queue.id} publicada no RabbitMQ para processamento")
                
            except Exception as e:
                logger.error(
                    f"⚠️ Erro ao publicar queue no RabbitMQ (queue será processada depois): {e}",
                    exc_info=True
                )
                # Não falha a criação da campanha se o RabbitMQ estiver offline
                # O consumer pode buscar queues pendentes periodicamente
            
            logger.info(
                f"✅ Billing campaign criada: {billing_campaign.id} "
                f"({len(contacts_created)} contatos)"
            )
            
            return True, billing_campaign, "Campanha criada com sucesso"
        
        except Exception as e:
            logger.error(f"❌ Erro ao criar billing campaign: {e}", exc_info=True)
            return False, None, f"Erro interno: {str(e)}"
    
    def _validate_request(
        self,
        template_type: str,
        contacts_data: List[Dict],
        external_id: Optional[str]
    ) -> Tuple[bool, str]:
        """Validações gerais"""
        
        # Verifica template_type
        valid_types = ['overdue', 'upcoming', 'notification']
        if template_type not in valid_types:
            return False, f"template_type inválido. Use: {', '.join(valid_types)}"
        
        # Verifica contatos
        if not contacts_data or len(contacts_data) == 0:
            return False, "Lista de contatos vazia"
        
        # Verifica external_id duplicado (se fornecido)
        if external_id:
            if BillingCampaign.objects.filter(
                tenant=self.tenant,
                external_id=external_id
            ).exists():
                return False, f"external_id '{external_id}' já existe"
        
        return True, ""
    
    def _get_template(self, template_type: str) -> Optional[BillingTemplate]:
        """Busca template ativo"""
        return BillingTemplate.objects.filter(
            tenant=self.tenant,
            template_type=template_type,
            is_active=True
        ).first()
    
    def _create_base_campaign(
        self,
        template_type: str,
        contacts_count: int,
        instance_id: Optional[str]
    ) -> Campaign:
        """Cria Campaign base (reutiliza infraestrutura)"""
        from apps.notifications.models import WhatsAppInstance
        
        # Nome da campanha
        campaign_name = f"Billing {template_type} - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Cria Campaign
        campaign = Campaign.objects.create(
            tenant=self.tenant,
            name=campaign_name,
            description=f"Campanha de billing gerada automaticamente ({template_type})",
            status='scheduled',
            rotation_mode='intelligent'
        )
        
        # Adiciona instância se fornecida
        if instance_id:
            try:
                instance = WhatsAppInstance.objects.get(id=instance_id, tenant=self.tenant)
                campaign.instances.add(instance)
            except WhatsAppInstance.DoesNotExist:
                logger.warning(f"Instância {instance_id} não encontrada, campanha criada sem instância")
        
        return campaign
    
    def _create_contacts(
        self,
        billing_campaign: BillingCampaign,
        campaign: Campaign,
        template: BillingTemplate,
        contacts_data: List[Dict[str, Any]]
    ) -> List[BillingContact]:
        """Cria contatos em batch"""
        from apps.contacts.models import Contact
        
        billing_contacts = []
        campaign_contacts_to_create = []
        billing_contacts_to_create = []
        
        # Busca variações ativas do template
        variations = list(
            BillingTemplateVariation.objects.filter(
                template=template,
                is_active=True
            ).order_by('order')
        )
        
        if not variations:
            raise ValueError(f"Template {template.id} não tem variações ativas")
        
        for idx, contact_data in enumerate(contacts_data):
            try:
                # Normaliza telefone
                phone = contact_data.get('telefone') or contact_data.get('phone')
                if not phone:
                    logger.warning(f"Contato {idx} sem telefone, pulando")
                    continue
                
                phone_normalized = normalize_phone(phone)
                if not phone_normalized:
                    logger.warning(f"Telefone inválido: {phone}, pulando")
                    continue
                
                # Busca ou cria Contact
                contact, _ = Contact.objects.get_or_create(
                    tenant=self.tenant,
                    phone=phone_normalized,
                    defaults={
                        'name': contact_data.get('nome') or contact_data.get('name', 'Cliente')
                    }
                )
                
                # Enriquece variáveis
                variables = self._enrich_variables(contact_data, template.template_type)
                
                # Seleciona variação (rotação)
                variation = self._select_variation(variations, idx)
                
                # Renderiza mensagem
                rendered_message = self.template_engine.render(
                    variation.template_text,
                    variables,
                    strict=False
                )
                
                # Cria CampaignContact (reutiliza)
                campaign_contact = CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    status='pending',
                    scheduled_at=timezone.now()
                )
                campaign_contacts_to_create.append(campaign_contact)
                
                # Cria BillingContact
                billing_contact = BillingContact(
                    billing_campaign=billing_campaign,
                    template_variation=variation,
                    status='pending',
                    rendered_message=rendered_message,
                    billing_data=contact_data
                )
                billing_contacts_to_create.append(billing_contact)
                
            except Exception as e:
                logger.error(f"Erro ao processar contato {idx}: {e}", exc_info=True)
                continue
        
        # Bulk create CampaignContacts
        CampaignContact.objects.bulk_create(campaign_contacts_to_create, batch_size=500)
        
        # Relaciona BillingContact com CampaignContact
        for i, billing_contact in enumerate(billing_contacts_to_create):
            billing_contact.campaign_contact = campaign_contacts_to_create[i]
        
        # Bulk create BillingContacts
        BillingContact.objects.bulk_create(billing_contacts_to_create, batch_size=500)
        
        logger.info(f"✅ Criados {len(billing_contacts_to_create)} contatos de billing")
        return billing_contacts_to_create
    
    def _enrich_variables(
        self,
        contact_data: Dict[str, Any],
        template_type: str
    ) -> Dict[str, Any]:
        """Enriquece variáveis com dados calculados"""
        variables = {
            'nome_cliente': contact_data.get('nome') or contact_data.get('name', 'Cliente'),
            'primeiro_nome': (contact_data.get('nome') or contact_data.get('name', 'Cliente')).split()[0],
            'valor': self._format_currency(contact_data.get('valor') or contact_data.get('value', '0')),
        }
        
        # Data de vencimento
        data_vencimento = contact_data.get('data_vencimento') or contact_data.get('due_date')
        if data_vencimento:
            if isinstance(data_vencimento, str):
                from datetime import datetime
                try:
                    data_vencimento = datetime.fromisoformat(data_vencimento.replace('Z', '+00:00'))
                except:
                    try:
                        data_vencimento = datetime.strptime(data_vencimento, '%Y-%m-%d')
                    except:
                        data_vencimento = None
            
            if data_vencimento:
                variables['data_vencimento'] = self.date_calculator.format_date_for_template(data_vencimento)
                
                # Calcula dias (depende do tipo)
                if template_type == 'overdue':
                    variables['dias_atraso'] = str(self.date_calculator.calculate_days_overdue(data_vencimento))
                elif template_type == 'upcoming':
                    variables['dias_vencimento'] = str(self.date_calculator.calculate_days_until_due(data_vencimento))
        
        # Campos opcionais (só aparecem se fornecidos)
        if contact_data.get('link_pagamento') or contact_data.get('payment_link'):
            variables['link_pagamento'] = contact_data.get('link_pagamento') or contact_data.get('payment_link')
        
        if contact_data.get('codigo_pix') or contact_data.get('pix_code'):
            variables['codigo_pix'] = contact_data.get('codigo_pix') or contact_data.get('pix_code')
        
        if contact_data.get('observacoes') or contact_data.get('notes'):
            variables['observacoes'] = contact_data.get('observacoes') or contact_data.get('notes')
        
        return variables
    
    def _select_variation(
        self,
        variations: List[BillingTemplateVariation],
        contact_index: int
    ) -> BillingTemplateVariation:
        """Seleciona variação usando rotação (round-robin)"""
        if not variations:
            raise ValueError("Nenhuma variação disponível")
        
        # Round-robin simples
        return variations[contact_index % len(variations)]
    
    @staticmethod
    def _format_currency(value: Any) -> str:
        """Formata valor como moeda"""
        try:
            if isinstance(value, str):
                value = float(value.replace(',', '.'))
            return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except:
            return f"R$ {value}"



