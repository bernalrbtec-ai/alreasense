"""
Celery tasks para processamento de campanhas
"""
from celery import shared_task
from django.utils import timezone
from .models import Campaign, CampaignLog
from .services import CampaignSender


@shared_task(bind=True, max_retries=3)
def process_campaign(self, campaign_id: str):
    """
    Processa uma campanha, enviando mensagens de forma assíncrona
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        print(f"❌ Campanha {campaign_id} não encontrada")
        return
    
    print(f"\n{'='*70}")
    print(f"🚀 Processando Campanha: {campaign.name}")
    print(f"{'='*70}")
    
    # Verificar se campanha está rodando
    if campaign.status != 'running':
        print(f"⚠️ Campanha não está rodando (status: {campaign.status})")
        return
    
    sender = CampaignSender(campaign)
    
    # Processar em lotes
    batch_size = 10
    total_sent = 0
    total_failed = 0
    
    while campaign.status == 'running':
        # ⚠️ CRÍTICO: Recarregar campanha ANTES de processar lote
        campaign.refresh_from_db()
        
        print(f"🔄 Verificando status da campanha: {campaign.status}")
        
        # Verificar se foi pausada/cancelada
        if campaign.status != 'running':
            print(f"⏸️ Campanha pausada ou cancelada (status: {campaign.status})")
            break
        
        # Processar lote
        results = sender.process_batch(batch_size)
        
        total_sent += results['sent']
        total_failed += results['failed']
        
        print(f"\n📊 Lote processado:")
        print(f"   ✅ Enviadas: {results['sent']}")
        print(f"   ❌ Falhas: {results['failed']}")
        print(f"   ⏭️ Puladas: {results['skipped']}")
        
        # Verificar se foi pausada durante o lote
        if results.get('paused', False):
            print(f"⏸️ Campanha foi pausada durante o processamento do lote")
            break
        
        # ⚠️ Verificar novamente após processar lote
        campaign.refresh_from_db()
        if campaign.status != 'running':
            print(f"⏸️ Campanha pausada após o lote (status: {campaign.status})")
            break
        
        # Se não há mais mensagens para enviar
        if results.get('completed', False):
            print("\n✅ Todos os contatos processados!")
            campaign.complete()
            break
        
        # Se não há mais contatos pendentes (sem completar)
        if results['skipped'] > 0:
            print("\n⚠️ Nenhum contato pendente encontrado!")
            break
        
        # Pequena pausa entre lotes
        import time
        time.sleep(2)
    
    print(f"\n{'='*70}")
    print(f"📊 RESUMO DA CAMPANHA: {campaign.name}")
    print(f"{'='*70}")
    print(f"✅ Total enviado: {total_sent}")
    print(f"❌ Total falhas: {total_failed}")
    print(f"📈 Taxa de sucesso: {(total_sent / (total_sent + total_failed) * 100) if (total_sent + total_failed) > 0 else 0:.1f}%")
    print(f"{'='*70}\n")


@shared_task
def send_single_message(campaign_id: str, contact_id: str):
    """
    Envia uma única mensagem
    Útil para retry individual
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        sender = CampaignSender(campaign)
        
        # Aqui você implementaria lógica para enviar para um contato específico
        success, message = sender.send_next_message()
        
        return {'success': success, 'message': message}
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        return {'success': False, 'message': str(e)}


@shared_task
def update_campaign_stats(campaign_id: str):
    """
    Atualiza estatísticas da campanha
    Pode ser executado periodicamente
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Recalcular contadores baseado em CampaignContact
        from django.db.models import Count, Q
        
        stats = campaign.campaign_contacts.aggregate(
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            read=Count('id', filter=Q(status='read')),
            failed=Count('id', filter=Q(status='failed'))
        )
        
        campaign.messages_sent = stats['sent']
        campaign.messages_delivered = stats['delivered']
        campaign.messages_read = stats['read']
        campaign.messages_failed = stats['failed']
        campaign.save()
        
        print(f"📊 Stats atualizadas para campanha: {campaign.name}")
        
        return stats
    except Exception as e:
        print(f"❌ Erro ao atualizar stats: {e}")
        return None


@shared_task
def check_campaign_health():
    """
    Verifica saúde de todas as campanhas ativas
    Pode ser executado via Celery Beat a cada 5 minutos
    """
    from apps.notifications.models import WhatsAppInstance
    
    active_campaigns = Campaign.objects.filter(status='running')
    
    for campaign in active_campaigns:
        # Verificar instâncias
        for instance in campaign.instances.all():
            instance.reset_daily_counters_if_needed()
            
            if not instance.is_healthy:
                CampaignLog.log_health_issue(
                    campaign, instance,
                    f"Health check falhou: score={instance.health_score}, errors={instance.consecutive_errors}"
                )
    
    print(f"✅ Health check completo: {active_campaigns.count()} campanhas verificadas")


@shared_task
def cleanup_old_logs(days: int = 30):
    """
    Remove logs antigos para economizar espaço
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    deleted = CampaignLog.objects.filter(
        created_at__lt=cutoff_date,
        severity='info'  # Manter errors e warnings
    ).delete()
    
    print(f"🗑️ Logs removidos: {deleted[0]} registros")
    
    return deleted[0]

