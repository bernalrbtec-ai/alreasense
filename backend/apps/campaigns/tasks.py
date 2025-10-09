from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import F
from django.core.cache import cache
import random
import requests

logger = get_task_logger(__name__)


@shared_task
def campaign_scheduler():
    """
    Task principal - roda a cada 10 segundos
    Busca campanhas prontas e enfileira envios
    """
    from apps.campaigns.models import Campaign, CampaignContact, CampaignMessage, CampaignLog
    from apps.campaigns.services import is_allowed_to_send, calculate_next_send_time
    
    now = timezone.now()
    
    # Buscar campanhas prontas
    ready_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        is_paused=False,
        next_scheduled_send__lte=now
    ).select_related('instance', 'tenant')
    
    logger.info(f"📊 {ready_campaigns.count()} campanhas prontas para processar")
    
    for campaign in ready_campaigns:
        try:
            # Heartbeat
            Campaign.objects.filter(id=campaign.id).update(last_heartbeat=now)
            
            # Validar horário
            can_send, reason = is_allowed_to_send(campaign, now)
            
            if not can_send:
                # Calcular próxima janela válida
                next_time = calculate_next_send_time(campaign, now)
                Campaign.objects.filter(id=campaign.id).update(
                    next_scheduled_send=next_time
                )
                logger.debug(f"⏭ {campaign.name}: Fora da janela ({reason}), próximo: {next_time}")
                continue
            
            # Pegar próximo contato pendente
            next_contact = CampaignContact.objects.filter(
                campaign=campaign,
                status=CampaignContact.Status.PENDING
            ).select_related('contact').first()
            
            if not next_contact:
                # Campanha concluída!
                campaign.status = Campaign.Status.COMPLETED
                campaign.completed_at = now
                campaign.save(update_fields=['status', 'completed_at'])
                
                CampaignLog.objects.create(
                    campaign=campaign,
                    level=CampaignLog.Level.SUCCESS,
                    event_type='campaign_completed',
                    message='Campanha concluída com sucesso',
                    metadata={
                        'total_contacts': campaign.total_contacts,
                        'sent_messages': campaign.sent_messages,
                        'response_rate': campaign.response_rate
                    }
                )
                logger.info(f"✅ {campaign.name}: Concluída!")
                continue
            
            # Selecionar mensagem (rotação)
            message = select_next_message(campaign)
            
            if not message:
                logger.error(f"❌ {campaign.name}: Sem mensagens ativas")
                campaign.is_paused = True
                campaign.auto_pause_reason = "Sem mensagens ativas"
                campaign.save(update_fields=['is_paused', 'auto_pause_reason'])
                continue
            
            # Renderizar mensagem
            rendered = message.render_variables(next_contact.contact, now)
            
            # Enfileirar task de envio
            send_message_task.apply_async(
                kwargs={
                    'campaign_id': str(campaign.id),
                    'contact_relation_id': str(next_contact.id),
                    'message_id': str(message.id),
                    'rendered_message': rendered
                }
            )
            
            # Calcular próximo envio (delay aleatório)
            delay = random.randint(
                campaign.instance.delay_min_seconds or 20,
                campaign.instance.delay_max_seconds or 50
            )
            next_send = now + timezone.timedelta(seconds=delay)
            Campaign.objects.filter(id=campaign.id).update(
                next_scheduled_send=next_send
            )
            
            logger.info(
                f"📤 {campaign.name}: Enfileirado envio para {next_contact.contact.name}, "
                f"próximo em {delay}s"
            )
            
        except Exception as e:
            logger.exception(f"❌ Erro ao processar {campaign.name}: {str(e)}")
            Campaign.objects.filter(id=campaign.id).update(
                is_paused=True,
                auto_pause_reason=f"Erro no scheduler: {str(e)}",
                last_error=str(e),
                last_error_at=now
            )
    
    return {
        'processed': ready_campaigns.count(),
        'timestamp': now.isoformat()
    }


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def send_message_task(self, campaign_id, contact_relation_id, message_id, rendered_message):
    """
    Envia uma mensagem via Evolution API
    """
    from apps.campaigns.models import Campaign, CampaignContact, CampaignMessage, CampaignLog
    from django.conf import settings
    
    try:
        # Buscar objetos
        campaign = Campaign.objects.select_related('instance', 'tenant').get(id=campaign_id)
        contact_relation = CampaignContact.objects.select_related('contact').get(id=contact_relation_id)
        message = CampaignMessage.objects.get(id=message_id)
        contact = contact_relation.contact
        
        # ⭐ Lock por telefone (anti-spam)
        lock_key = f'phone_lock:{contact.phone}'
        lock_acquired = cache.add(lock_key, campaign_id, timeout=60)
        
        if not lock_acquired:
            # Número em uso por outra campanha
            logger.warning(f"⏸ {contact.phone} em uso, reagendando em 20s")
            send_message_task.apply_async(
                kwargs={
                    'campaign_id': campaign_id,
                    'contact_relation_id': contact_relation_id,
                    'message_id': message_id,
                    'rendered_message': rendered_message
                },
                countdown=20
            )
            return {'status': 'deferred', 'reason': 'phone_in_use'}
        
        try:
            # Validações críticas
            campaign.refresh_from_db()
            
            if campaign.is_paused:
                logger.warning(f"🛑 {campaign.name} pausada, abortando")
                return {'status': 'aborted', 'reason': 'paused'}
            
            if campaign.status != Campaign.Status.ACTIVE:
                logger.warning(f"🛑 {campaign.name} não ativa (status={campaign.status})")
                return {'status': 'aborted', 'reason': 'not_active'}
            
            if campaign.instance.connection_state != 'open':
                logger.error(f"🛑 Instância {campaign.instance.friendly_name} desconectada")
                Campaign.objects.filter(id=campaign_id).update(
                    is_paused=True,
                    auto_pause_reason="Instância desconectada"
                )
                return {'status': 'aborted', 'reason': 'instance_disconnected'}
            
            # Enviar via Evolution API
            logger.info(f"📱 Enviando para {contact.name} ({contact.phone})")
            
            api_url = campaign.instance.api_url or settings.EVOLUTION_API_URL
            api_key = campaign.instance.api_key
            
            response = requests.post(
                f"{api_url}/message/sendText/{campaign.instance.evolution_instance_name}",
                json={
                    "number": contact.phone,
                    "text": rendered_message
                },
                headers={
                    "apikey": api_key,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Atualizar status
            CampaignContact.objects.filter(id=contact_relation_id).update(
                status=CampaignContact.Status.SENT,
                sent_at=timezone.now(),
                evolution_message_id=result.get('key', {}).get('id', ''),
                message_sent=message
            )
            
            # Incrementar contadores
            Campaign.objects.filter(id=campaign_id).update(
                sent_messages=F('sent_messages') + 1,
                last_send_at=timezone.now()
            )
            
            CampaignMessage.objects.filter(id=message_id).update(
                times_sent=F('times_sent') + 1
            )
            
            # Log
            CampaignLog.objects.create(
                campaign=campaign,
                contact=contact,
                level=CampaignLog.Level.SUCCESS,
                event_type='message_sent',
                message=f'Mensagem enviada para {contact.name}',
                metadata={
                    'evolution_response': result,
                    'message_length': len(rendered_message)
                }
            )
            
            logger.info(f"✅ Enviado com sucesso para {contact.name}")
            
            return {'status': 'success', 'message_id': result.get('key', {}).get('id')}
            
        finally:
            # SEMPRE liberar lock
            cache.delete(lock_key)
        
    except Campaign.DoesNotExist:
        logger.error(f"❌ Campanha {campaign_id} não encontrada")
        return {'status': 'error', 'reason': 'campaign_not_found'}
    
    except Exception as e:
        logger.exception(f"❌ Erro ao enviar mensagem: {str(e)}")
        
        # Marcar como falha
        CampaignContact.objects.filter(id=contact_relation_id).update(
            status=CampaignContact.Status.FAILED,
            error_message=str(e),
            retry_count=F('retry_count') + 1
        )
        
        Campaign.objects.filter(id=campaign_id).update(
            failed_messages=F('failed_messages') + 1,
            last_error=str(e),
            last_error_at=timezone.now()
        )
        
        CampaignLog.objects.create(
            campaign_id=campaign_id,
            contact_id=contact.id if 'contact' in locals() else None,
            level=CampaignLog.Level.ERROR,
            event_type='message_failed',
            message=f'Falha ao enviar: {str(e)}',
            metadata={'error': str(e), 'retry_attempt': self.request.retries}
        )
        
        # Retry se for erro temporário
        if isinstance(e, (ConnectionError, TimeoutError, requests.exceptions.Timeout)):
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        
        return {'status': 'error', 'reason': str(e)}


def select_next_message(campaign):
    """Seleciona próxima mensagem (round-robin balanceado)"""
    messages = campaign.messages.filter(
        is_active=True
    ).order_by('times_sent', 'order')
    
    return messages.first()

