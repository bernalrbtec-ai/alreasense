"""
Signals para invalidar cache quando departamentos são atualizados
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.common.cache_manager import CacheManager
from .models import Department

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Department)
@receiver(post_delete, sender=Department)
def invalidate_department_cache(sender, instance, **kwargs):
    """Invalidar cache de departamentos quando departamento é salvo ou deletado"""
    logger.info(f"🔄 [CACHE] Invalidando cache de departamentos após mudança em {instance.name}")
    
    # Invalidar cache de departamentos (todos os padrões)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_DEPARTMENT}:*")
