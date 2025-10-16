from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaigns'
    verbose_name = 'Campanhas'
    
    def ready(self):
        """App pronto - Recuperar campanhas ativas"""
        logger.info("✅ [APPS] App campanhas inicializado")
        
        # Recuperar campanhas ativas em thread separada para não bloquear startup
        def recover_active_campaigns():
            try:
                # Aguardar um pouco para garantir que o Django está totalmente carregado
                time.sleep(5)
                
                from .models import Campaign
                from .rabbitmq_consumer import get_rabbitmq_consumer
                
                # Buscar campanhas que realmente precisam ser processadas
                # Só recuperar campanhas que têm contatos pendentes E foram interrompidas por erro (não pelo usuário)
                from .models import CampaignContact
                
                campaigns_to_recover = []
                
                # Buscar campanhas que podem precisar de recuperação
                # 'running' = estava rodando quando o sistema parou (recuperar)
                # 'paused' = foi pausada pelo usuário (NÃO recuperar)
                # 'stopped' = foi parada pelo usuário (NÃO recuperar)
                active_campaigns = Campaign.objects.filter(status='running')
                
                for campaign in active_campaigns:
                    # Verificar se tem contatos pendentes
                    pending_contacts = CampaignContact.objects.filter(
                        campaign=campaign, 
                        status='pending'
                    ).count()
                    
                    if pending_contacts > 0:
                        campaigns_to_recover.append(campaign)
                        logger.info(f"🔄 [RECOVERY] Campanha {campaign.id} - {campaign.name} tem {pending_contacts} contatos pendentes - RECUPERANDO")
                    else:
                        logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} não tem contatos pendentes - marcando como concluída")
                        # Marcar como concluída se não tem contatos pendentes
                        campaign.status = 'completed'
                        campaign.save()
                
                # Verificar campanhas pausadas/paradas que podem ter sido afetadas
                user_stopped_campaigns = Campaign.objects.filter(status__in=['paused', 'stopped'])
                for campaign in user_stopped_campaigns:
                    pending_contacts = CampaignContact.objects.filter(
                        campaign=campaign, 
                        status='pending'
                    ).count()
                    
                    if pending_contacts > 0:
                        logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} tem {pending_contacts} contatos pendentes mas foi pausada/parada pelo usuário - MANTENDO status")
                    else:
                        logger.info(f"ℹ️ [RECOVERY] Campanha {campaign.id} - {campaign.name} foi pausada/parada pelo usuário e não tem contatos pendentes - MANTENDO status")
                
                if campaigns_to_recover:
                    logger.info(f"🔄 [RECOVERY] Encontradas {len(campaigns_to_recover)} campanhas para recuperar")
                    
                    consumer = get_rabbitmq_consumer()
                    
                    for campaign in campaigns_to_recover:
                        try:
                            logger.info(f"🚀 [RECOVERY] Recuperando campanha {campaign.id} - {campaign.name}")
                            success = consumer.start_campaign(str(campaign.id))
                            
                            if success:
                                logger.info(f"✅ [RECOVERY] Campanha {campaign.id} recuperada com sucesso")
                            else:
                                logger.error(f"❌ [RECOVERY] Falha ao recuperar campanha {campaign.id}")
                                
                        except Exception as e:
                            logger.error(f"❌ [RECOVERY] Erro ao recuperar campanha {campaign.id}: {e}")
                else:
                    logger.info("ℹ️ [RECOVERY] Nenhuma campanha com contatos pendentes encontrada")
                
                logger.info("✅ [RECOVERY] Processo de recuperação de campanhas concluído")
                    
            except Exception as e:
                logger.error(f"❌ [RECOVERY] Erro no processo de recuperação: {e}")
        
        # Iniciar thread de recuperação
        recovery_thread = threading.Thread(target=recover_active_campaigns, daemon=True)
        recovery_thread.start()
