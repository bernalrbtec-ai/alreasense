from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaigns'
    verbose_name = 'Campanhas'
    
    def ready(self):
        """Inicializa MongoDB quando o Django está pronto"""
        try:
            from .mongodb_client import mongodb_client
            mongodb_client.connect()
            logger.info("✅ [APPS] MongoDB inicializado para campanhas")
        except Exception as e:
            logger.error(f"❌ [APPS] Erro ao inicializar MongoDB: {e}")
