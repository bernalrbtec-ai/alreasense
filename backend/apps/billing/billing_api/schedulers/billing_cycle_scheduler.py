"""
BillingCycleScheduler - Scheduler para processar mensagens agendadas do ciclo
"""
from django.utils import timezone
from django.db import transaction
from datetime import datetime, date, time
import logging

from apps.billing.billing_api.billing_cycle import BillingCycle
from apps.billing.billing_api.billing_contact import BillingContact
from apps.billing.billing_api.utils.template_engine import BillingTemplateEngine
from apps.billing.billing_api.utils.date_calculator import BillingDateCalculator
from apps.billing.billing_api.rabbitmq.billing_publisher import BillingQueuePublisher

logger = logging.getLogger(__name__)


class BillingCycleScheduler:
    """
    Scheduler que processa mensagens agendadas do ciclo de billing
    """
    
    @staticmethod
    def process_scheduled_messages(batch_size: int = 100):
        """
        Processa mensagens agendadas que devem ser enviadas agora
        
        Args:
            batch_size: Quantidade de mensagens a processar por vez
        """
        now = timezone.now()
        today = now.date()
        
        # Busca mensagens pendentes agendadas para hoje ou antes
        messages = BillingContact.objects.filter(
            billing_cycle__isnull=False,
            status='pending',
            billing_status='active',
            scheduled_date__lte=today,
            scheduled_at__lte=now
        ).select_for_update(
            skip_locked=True  # Evita lock de outras threads
        ).select_related(
            'billing_cycle',
            'billing_cycle__tenant',
            'billing_cycle__contact',
            'template_variation',
            'template_variation__template'
        )[:batch_size]
        
        processed = 0
        errors = 0
        
        for billing_contact in messages:
            try:
                with transaction.atomic():
                    # Lock otimista: verifica versão
                    current_version = billing_contact.version
                    billing_contact.refresh_from_db()
                    
                    if billing_contact.version != current_version:
                        # Foi modificado por outro processo, pula
                        logger.debug(
                            f"⏭️ Mensagem {billing_contact.id} foi modificada, pulando"
                        )
                        continue
                    
                    # Verifica se ciclo ainda está ativo
                    cycle = billing_contact.billing_cycle
                    if cycle.status not in ['active']:
                        billing_contact.status = 'cancelled'
                        billing_contact.billing_status = cycle.status
                        billing_contact.save(update_fields=['status', 'billing_status', 'updated_at'])
                        logger.info(
                            f"❌ Mensagem {billing_contact.id} cancelada: ciclo {cycle.status}"
                        )
                        continue
                    
                    # Valida template_variation
                    if not billing_contact.template_variation:
                        logger.error(
                            f"❌ Mensagem {billing_contact.id} não tem template_variation",
                            extra={'billing_contact_id': str(billing_contact.id)}
                        )
                        billing_contact.status = 'failed'
                        billing_contact.billing_data['last_error'] = 'Template variation não encontrado'
                        billing_contact.save(update_fields=['status', 'billing_data', 'updated_at'])
                        errors += 1
                        continue
                    
                    # Renderiza template
                    template_text = billing_contact.template_variation.template_text
                    billing_data = billing_contact.billing_data or {}
                    
                    # Calcula variáveis dinâmicas
                    due_date = cycle.due_date
                    days_overdue = BillingDateCalculator.calculate_days_overdue(due_date)
                    days_until_due = BillingDateCalculator.calculate_days_until_due(due_date)
                    
                    # Prepara contexto com validação de tipos
                    try:
                        # Formata valor monetário
                        value = billing_data.get('value', 0)
                        if isinstance(value, (int, float)):
                            value_str = f"R$ {float(value):.2f}"
                        else:
                            # Tenta converter string para float
                            try:
                                value_str = f"R$ {float(str(value).replace(',', '.')):.2f}"
                            except (ValueError, AttributeError):
                                value_str = f"R$ {0:.2f}"
                                logger.warning(
                                    f"⚠️ Valor inválido na billing_data: {value}, usando 0.00"
                                )
                    except Exception as e:
                        logger.error(f"❌ Erro ao formatar valor: {e}")
                        value_str = "R$ 0.00"
                    
                    # Prepara contexto
                    context = {
                        'nome_cliente': cycle.contact_name or 'Cliente',
                        'valor': value_str,
                        'data_vencimento': BillingDateCalculator.format_date_for_template(due_date),
                        'dias_atraso': str(days_overdue) if days_overdue > 0 else '0',
                        'dias_vencimento': str(days_until_due) if days_until_due > 0 else '0',
                    }
                    
                    # Adiciona campos opcionais
                    if billing_data.get('link_pagamento'):
                        context['link_pagamento'] = billing_data['link_pagamento']
                    if billing_data.get('codigo_pix'):
                        context['codigo_pix'] = billing_data['codigo_pix']
                    if billing_data.get('observacoes'):
                        context['observacoes'] = billing_data['observacoes']
                    
                    # Renderiza mensagem
                    engine = BillingTemplateEngine()
                    rendered_message = engine.render(template_text, context)
                    
                    # Valida tamanho (WhatsApp: 4096 caracteres)
                    if len(rendered_message) > 4096:
                        logger.error(
                            f"❌ Mensagem {billing_contact.id} excede 4096 caracteres: {len(rendered_message)}"
                        )
                        billing_contact.status = 'failed'
                        billing_contact.billing_data['last_error'] = 'Mensagem excede limite de 4096 caracteres'
                        billing_contact.save(update_fields=['status', 'billing_data', 'updated_at'])
                        errors += 1
                        continue
                    
                    # Busca instância ativa do tenant
                    from apps.instances.models import Instance
                    instance = Instance.objects.filter(
                        tenant=cycle.tenant,
                        is_active=True
                    ).first()
                    
                    if not instance:
                        logger.error(
                            f"❌ Instância ativa não encontrada para tenant {cycle.tenant.id}"
                        )
                        billing_contact.status = 'failed'
                        billing_contact.billing_data['last_error'] = 'Instância ativa não encontrada'
                        billing_contact.save(update_fields=['status', 'billing_data', 'updated_at'])
                        errors += 1
                        continue
                    
                    contact = cycle.contact
                    if not contact:
                        logger.error(
                            f"❌ Contato não encontrado para ciclo {cycle.id}",
                            extra={'cycle_id': str(cycle.id)}
                        )
                        billing_contact.status = 'failed'
                        billing_contact.billing_data['last_error'] = 'Contato não encontrado no ciclo'
                        billing_contact.save(update_fields=['status', 'billing_data', 'updated_at'])
                        errors += 1
                        continue
                    
                    # IMPORTANTE: Para mensagens de ciclo, não precisamos de CampaignContact
                    # porque não são parte de uma campanha tradicional. A mensagem será enviada
                    # diretamente via WhatsApp API usando a instância e o contato.
                    # O billing_contact.campaign_contact pode ficar None.
                    
                    # Atualiza BillingContact com mensagem renderizada
                    billing_contact.rendered_message = rendered_message
                    billing_contact.status = 'sending'
                    billing_contact.version += 1
                    billing_contact.save(update_fields=[
                        'rendered_message',
                        'status',
                        'version',
                        'updated_at'
                    ])
                    
                    # TODO: Implementar envio de mensagem
                    # Opções:
                    # 1. Usar Evolution API diretamente
                    # 2. Criar queue específica para ciclos (billing.cycle)
                    # 3. Criar BillingQueue individual para cada mensagem
                    #
                    # Por enquanto, mensagem fica como 'sending' e será processada
                    # por um consumer específico ou task periódica que processa
                    # BillingContact com status='sending' e billing_cycle não nulo.
                    #
                    # Exemplo de implementação (Opção 1 - Evolution API direto):
                    # from apps.notifications.utils.evolution_api import EvolutionAPI
                    # api = EvolutionAPI.get_for_instance(instance)
                    # result = api.send_text_message(contact.phone, rendered_message)
                    
                    logger.info(
                        f"📤 Mensagem {billing_contact.id} pronta para envio: {cycle.external_billing_id}",
                        extra={
                            'billing_contact_id': str(billing_contact.id),
                            'cycle_id': str(cycle.id),
                            'external_billing_id': cycle.external_billing_id,
                            'instance_id': str(instance.id),
                            'contact_phone': contact.phone
                        }
                    )
                    
                    processed += 1
                    
            except Exception as e:
                logger.error(
                    f"❌ Erro ao processar mensagem {billing_contact.id}: {e}",
                    exc_info=True
                )
                errors += 1
        
        if processed > 0 or errors > 0:
            logger.info(
                f"📊 Scheduler processou: {processed} enviadas, {errors} erros",
                extra={'processed': processed, 'errors': errors}
            )
        
        return processed, errors
    
    @staticmethod
    def check_and_complete_cycles():
        """
        Verifica e completa ciclos finalizados
        """
        cycles = BillingCycle.objects.filter(
            status='active'
        ).exclude(
            billing_contacts__status__in=['pending', 'pending_retry', 'sending']
        )
        
        completed = 0
        for cycle in cycles:
            if cycle.check_and_complete():
                completed += 1
        
        if completed > 0:
            logger.info(f"✅ {completed} ciclos completados")

