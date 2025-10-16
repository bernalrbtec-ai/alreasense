from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaigns'
    verbose_name = 'Campanhas'
    
    def ready(self):
        """App pronto - MongoDB removido"""
        logger.info("✅ [APPS] App campanhas inicializado")
