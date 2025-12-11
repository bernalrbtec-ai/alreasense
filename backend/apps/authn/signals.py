"""
Signals para invalidar cache quando departamentos e usuários são atualizados
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.common.cache_manager import CacheManager
from .models import Department, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Department)
@receiver(post_delete, sender=Department)
def invalidate_department_cache(sender, instance, **kwargs):
    """Invalidar cache de departamentos quando departamento é salvo ou deletado"""
    logger.info(f"🔄 [CACHE] Invalidando cache de departamentos após mudança em {instance.name}")
    
    # Invalidar cache de departamentos (todos os padrões)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_DEPARTMENT}:*")


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    """Invalidar cache de usuários quando usuário é salvo ou deletado"""
    logger.info(f"🔄 [CACHE] Invalidando cache de usuários após mudança em {instance.email}")
    
    # Invalidar cache de usuários (todos os padrões)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_USER}:*")
