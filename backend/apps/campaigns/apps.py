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
                
                # Buscar campanhas ativas
                active_campaigns = Campaign.objects.filter(status__in=['active', 'running'])
                
                if active_campaigns.exists():
                    logger.info(f"🔄 [RECOVERY] Encontradas {active_campaigns.count()} campanhas ativas para recuperar")
                    
                    consumer = get_rabbitmq_consumer()
                    
                    for campaign in active_campaigns:
                        try:
                            logger.info(f"🚀 [RECOVERY] Recuperando campanha {campaign.id} - {campaign.name}")
                            success = consumer.start_campaign(str(campaign.id))
                            
                            if success:
                                logger.info(f"✅ [RECOVERY] Campanha {campaign.id} recuperada com sucesso")
                            else:
                                logger.error(f"❌ [RECOVERY] Falha ao recuperar campanha {campaign.id}")
                                
                        except Exception as e:
                            logger.error(f"❌ [RECOVERY] Erro ao recuperar campanha {campaign.id}: {e}")
                    
                    logger.info("✅ [RECOVERY] Processo de recuperação de campanhas concluído")
                else:
                    logger.info("ℹ️ [RECOVERY] Nenhuma campanha ativa encontrada para recuperar")
                    
            except Exception as e:
                logger.error(f"❌ [RECOVERY] Erro no processo de recuperação: {e}")
        
        # Iniciar thread de recuperação
        recovery_thread = threading.Thread(target=recover_active_campaigns, daemon=True)
        recovery_thread.start()
