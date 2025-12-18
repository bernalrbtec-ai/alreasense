"""
BillingCycleService - Service para gerenciar ciclos de mensagens de cobrança
"""
from django.db import transaction, IntegrityError
from django.utils import timezone
from datetime import timedelta, date, time, datetime
import logging
import re

from apps.contacts.models import Contact, Tag
from apps.billing.billing_api.billing_cycle import BillingCycle
from apps.billing.billing_api.billing_contact import BillingContact
from apps.billing.billing_api.billing_template import BillingTemplate, BillingTemplateVariation
from apps.billing.billing_api.utils.date_calculator import DateCalculator
from apps.billing.billing_api.utils.template_engine import BillingTemplateEngine

logger = logging.getLogger(__name__)


class BillingCycleService:
    """
    Service para criar e gerenciar ciclos de mensagens de cobrança
    """
    
    # Dias para mensagens upcoming (antes do vencimento)
    UPCOMING_DAYS = [5, 3, 1]
    
    # Dias para mensagens overdue (depois do vencimento)
    OVERDUE_DAYS = [1, 3, 5]
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normaliza telefone para formato E.164
        
        Args:
            phone: Telefone em qualquer formato
        
        Returns:
            Telefone normalizado no formato E.164 (ex: +5511999999999)
        
        Raises:
            ValueError: Se telefone for inválido ou vazio
        """
        if not phone or not isinstance(phone, str):
            raise ValueError('Telefone é obrigatório e deve ser uma string')
        
        # Remove espaços e caracteres não numéricos (exceto +)
        phone = re.sub(r'[^\d+]', '', phone.strip())
        
        if not phone or len(phone) < 10:
            raise ValueError(f'Telefone inválido: {phone}')
        
        # Se não começa com +, adiciona +55 (Brasil)
        if not phone.startswith('+'):
            if phone.startswith('55'):
                phone = '+' + phone
            elif phone.startswith('0'):
                phone = '+55' + phone[1:]
            else:
                phone = '+55' + phone
        
        # Valida formato E.164 básico (mínimo 10 dígitos após +)
        if not re.match(r'^\+\d{10,15}$', phone):
            raise ValueError(f'Telefone não está no formato E.164 válido: {phone}')
        
        return phone
    
    @staticmethod
    @transaction.atomic
    def get_or_create_contact(tenant, phone: str, name: str) -> Contact:
        """
        Busca ou cria contato e adiciona tag COBRANÇA
        
        Args:
            tenant: Tenant do contato
            phone: Telefone do contato
            name: Nome do contato
        
        Returns:
            Contact: Contato criado ou existente
        
        Raises:
            ValueError: Se telefone ou nome forem inválidos
        """
        if not name or not isinstance(name, str) or len(name.strip()) == 0:
            raise ValueError('Nome do contato é obrigatório')
        
        try:
            phone_normalized = BillingCycleService.normalize_phone(phone)
        except ValueError as e:
            logger.error(f"❌ Erro ao normalizar telefone {phone}: {e}")
            raise
        
        # Busca contato existente
        contact = Contact.objects.filter(
            tenant=tenant,
            phone=phone_normalized
        ).first()
        
        if contact:
            # Atualiza nome se mudou
            if contact.name != name:
                contact.name = name
                contact.save(update_fields=['name', 'updated_at'])
                logger.info(f"📝 Contato {contact.id} atualizado: {name}")
            
            # Adiciona tag COBRANÇA se não tiver
            tag, _ = Tag.objects.get_or_create(
                tenant=tenant,
                name='COBRANÇA',
                defaults={
                    'color': '#EF4444',
                    'description': 'Contato com cobrança ativa'
                }
            )
            if tag not in contact.tags.all():
                contact.tags.add(tag)
                logger.info(f"🏷️ Tag COBRANÇA adicionada ao contato {contact.id}")
        else:
            # Cria novo contato
            contact = Contact.objects.create(
                tenant=tenant,
                phone=phone_normalized,
                name=name
            )
            
            # Adiciona tag COBRANÇA
            tag, _ = Tag.objects.get_or_create(
                tenant=tenant,
                name='COBRANÇA',
                defaults={
                    'color': '#EF4444',
                    'description': 'Contato com cobrança ativa'
                }
            )
            contact.tags.add(tag)
            
            logger.info(f"✅ Contato criado: {contact.id} ({name})")
        
        return contact
    
    @staticmethod
    @transaction.atomic
    def create_cycle(
        tenant,
        external_billing_id: str,
        contact_phone: str,
        contact_name: str,
        due_date: date,
        billing_data: dict,
        notify_before_due: bool = False,
        notify_after_due: bool = True
    ) -> BillingCycle:
        """
        Cria ciclo de mensagens com proteção contra duplicação
        """
        try:
            # Normaliza telefone antes de criar ciclo
            try:
                normalized_phone = BillingCycleService.normalize_phone(contact_phone)
            except ValueError as e:
                logger.error(f"❌ Erro ao normalizar telefone {contact_phone}: {e}")
                raise
            
            # Tenta criar ciclo (unique_together: tenant + external_billing_id)
            cycle = BillingCycle.objects.create(
                tenant=tenant,
                external_billing_id=external_billing_id,
                contact_phone=normalized_phone,  # Usa telefone normalizado
                contact_name=contact_name,
                due_date=due_date,
                billing_data=billing_data,
                notify_before_due=notify_before_due,
                notify_after_due=notify_after_due,
                status='active'
            )
            
            # Cria ou atualiza contato
            try:
                contact = BillingCycleService.get_or_create_contact(
                    tenant, normalized_phone, contact_name
                )
                cycle.contact = contact
                cycle.save(update_fields=['contact'])
            except ValueError as e:
                # Se falhar ao criar contato, loga mas continua (ciclo pode funcionar sem contato linkado)
                logger.warning(
                    f"⚠️ Erro ao criar/atualizar contato: {e}, ciclo continuará sem contato linkado",
                    extra={'cycle_id': str(cycle.id), 'error': str(e)}
                )
            
            logger.info(
                f"✅ Ciclo criado: {cycle.id} - {external_billing_id}",
                extra={'cycle_id': str(cycle.id), 'tenant_id': str(tenant.id)}
            )
            
            return cycle
            
        except IntegrityError:
            # Ciclo já existe - retorna existente
            cycle = BillingCycle.objects.get(
                tenant=tenant,
                external_billing_id=external_billing_id
            )
            
            logger.warning(
                f"⚠️ Ciclo já existe: {cycle.id} - {external_billing_id}",
                extra={'cycle_id': str(cycle.id), 'tenant_id': str(tenant.id)}
            )
            
            # Se foi cancelado/pago, reativa
            if cycle.status in ['cancelled', 'paid']:
                cycle.status = 'active'
                cycle.cancelled_at = None
                cycle.completed_at = None
                cycle.save(update_fields=['status', 'cancelled_at', 'completed_at', 'updated_at'])
                logger.info(f"🔄 Ciclo reativado: {cycle.id}")
            
            return cycle
    
    @staticmethod
    def calculate_message_dates(due_date: date, notify_before: bool, notify_after: bool) -> list:
        """
        Calcula datas das 6 mensagens do ciclo
        
        Returns:
            Lista de tuplas (message_type, days_offset, target_date)
            Ex: [('upcoming_5d', -5, date(2025, 1, 10)), ...]
        """
        messages = []
        
        # Mensagens upcoming (antes do vencimento)
        if notify_before:
            for days in BillingCycleService.UPCOMING_DAYS:
                target_date = due_date - timedelta(days=days)
                messages.append((
                    f'upcoming_{days}d',
                    -days,
                    target_date
                ))
        
        # Mensagens overdue (depois do vencimento)
        if notify_after:
            for days in BillingCycleService.OVERDUE_DAYS:
                target_date = due_date + timedelta(days=days)
                messages.append((
                    f'overdue_{days}d',
                    days,
                    target_date
                ))
        
        return messages
    
    @staticmethod
    @transaction.atomic
    def schedule_cycle_messages(cycle: BillingCycle):
        """
        Agenda todas as mensagens do ciclo
        
        IMPORTANTE: Se o ciclo já tiver mensagens agendadas, não cria duplicatas.
        Isso permite reativar ciclos cancelados sem duplicar mensagens.
        """
        # Verifica se ciclo já tem mensagens agendadas
        existing_messages = BillingContact.objects.filter(
            billing_cycle=cycle
        ).count()
        
        if existing_messages > 0:
            logger.info(
                f"⏭️ Ciclo {cycle.id} já tem {existing_messages} mensagens agendadas, pulando agendamento",
                extra={'cycle_id': str(cycle.id), 'existing_count': existing_messages}
            )
            return
        
        # Busca templates ativos do tenant
        upcoming_template = BillingTemplate.objects.filter(
            tenant=cycle.tenant,
            template_type='upcoming',
            is_active=True
        ).first()
        
        overdue_template = BillingTemplate.objects.filter(
            tenant=cycle.tenant,
            template_type='overdue',
            is_active=True
        ).first()
        
        if not upcoming_template and cycle.notify_before_due:
            logger.warning(
                f"⚠️ Template 'upcoming' não encontrado para tenant {cycle.tenant.id}"
            )
        
        if not overdue_template and cycle.notify_after_due:
            logger.warning(
                f"⚠️ Template 'overdue' não encontrado para tenant {cycle.tenant.id}"
            )
        
        # Calcula datas das mensagens
        message_dates = BillingCycleService.calculate_message_dates(
            cycle.due_date,
            cycle.notify_before_due,
            cycle.notify_after_due
        )
        
        cycle.total_messages = len(message_dates)
        cycle.save(update_fields=['total_messages'])
        
        # Agenda cada mensagem
        for index, (message_type, days_offset, target_date) in enumerate(message_dates, 1):
            # Determina template
            if message_type.startswith('upcoming'):
                template = upcoming_template
            else:
                template = overdue_template
            
            if not template:
                logger.warning(
                    f"⚠️ Template não encontrado para {message_type}, pulando mensagem"
                )
                continue
            
            # Busca variação ativa (rotação circular baseada no índice)
            # Usa módulo para rotacionar entre variações disponíveis
            variations = list(BillingTemplateVariation.objects.filter(
                template=template,
                is_active=True
            ).order_by('order'))
            
            if not variations:
                logger.warning(
                    f"⚠️ Nenhuma variação ativa para template {template.id}, pulando mensagem",
                    extra={'template_id': str(template.id), 'cycle_id': str(cycle.id)}
                )
                continue
            
            # Rotação circular: usa índice da mensagem para escolher variação
            variation_index = (index - 1) % len(variations)
            variation = variations[variation_index]
            
            # Calcula data ajustada (dia útil, horário comercial)
            # Para overdue, posterga; para upcoming, antecipa
            is_overdue = message_type.startswith('overdue')
            adjusted_date = DateCalculator.calculate_send_date(
                target_date,
                cycle.tenant,
                is_overdue=is_overdue
            )
            
            # Calcula datetime (data + horário comercial)
            send_datetime = datetime.combine(
                adjusted_date,
                time(9, 0)  # 9h da manhã
            )
            send_datetime = timezone.make_aware(send_datetime)
            
            # Cria BillingContact para mensagem agendada
            BillingContact.objects.create(
                billing_cycle=cycle,
                billing_campaign=None,  # Mensagem agendada, não de campanha
                campaign_contact=None,  # Será criado no envio
                template_variation=variation,
                status='pending',
                billing_data=cycle.billing_data,
                cycle_message_type=message_type,
                cycle_index=index,
                scheduled_date=adjusted_date,
                scheduled_at=send_datetime,
                billing_status='active',
                version=0
            )
            
            logger.info(
                f"📅 Mensagem {index} agendada: {message_type} para {adjusted_date}",
                extra={
                    'cycle_id': str(cycle.id),
                    'message_type': message_type,
                    'scheduled_date': str(adjusted_date)
                }
            )
        
        logger.info(
            f"✅ Ciclo {cycle.id} agendado: {len(message_dates)} mensagens",
            extra={'cycle_id': str(cycle.id), 'total_messages': len(message_dates)}
        )
    
    @staticmethod
    @transaction.atomic
    def cancel_cycle(tenant, external_billing_id: str, reason: str = 'cancelled'):
        """
        Cancela ciclo e todas as mensagens pendentes
        """
        try:
            cycle = BillingCycle.objects.select_for_update().get(
                tenant=tenant,
                external_billing_id=external_billing_id
            )
            
            if cycle.status in ['cancelled', 'paid', 'completed']:
                logger.warning(
                    f"⚠️ Ciclo {cycle.id} já está {cycle.status}"
                )
                return cycle
            
            # Atualiza status do ciclo
            cycle.status = reason  # 'cancelled' ou 'paid'
            cycle.cancelled_at = timezone.now()
            cycle.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            
            # Cancela mensagens pendentes (incluindo 'sending' que ainda não foram enviadas)
            # Não cancela mensagens já enviadas (sent, delivered, read)
            cancelled_count = BillingContact.objects.filter(
                billing_cycle=cycle,
                status__in=['pending', 'pending_retry', 'sending']
            ).update(
                billing_status=reason,
                status='cancelled'
            )
            
            logger.info(
                f"✅ Ciclo {cycle.id} cancelado: {cancelled_count} mensagens canceladas",
                extra={
                    'cycle_id': str(cycle.id),
                    'external_billing_id': external_billing_id,
                    'cancelled_count': cancelled_count
                }
            )
            
            return cycle
            
        except BillingCycle.DoesNotExist:
            logger.warning(
                f"⚠️ Ciclo não encontrado: {external_billing_id}",
                extra={'external_billing_id': external_billing_id, 'tenant_id': str(tenant.id)}
            )
            return None

