import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.tenancy.models import Tenant
from apps.common.cache_manager import CacheManager
from .models import WhatsAppInstance

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """Send welcome notification when a new user is created."""
    if created and instance.email:
        # TODO: Implementar notificação de boas-vindas com RabbitMQ
        logger.info(f"🎉 Novo usuário criado: {instance.email}")
        # send_welcome_notification.delay(instance.id)  # Removido - Celery deletado


@receiver(post_save, sender=WhatsAppInstance)
@receiver(post_delete, sender=WhatsAppInstance)
def invalidate_whatsapp_instance_cache(sender, instance, **kwargs):
    """Invalidar cache de instâncias WhatsApp quando instância é salva ou deletada"""
    logger.info(f"🔄 [CACHE] Invalidando cache de instâncias WhatsApp após mudança em {instance.friendly_name}")
    
    # Invalidar cache de instâncias (todos os padrões)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_INSTANCE}:*")


# Note: For plan change, you'll need to update the Tenant model save method
# or create a signal in the tenancy app to detect plan changes

