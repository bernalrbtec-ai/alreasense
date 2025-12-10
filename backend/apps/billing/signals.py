"""
Signals para invalidar cache quando produtos/planos são atualizados
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.common.cache_manager import CacheManager
from .models import Product, Plan, TenantProduct

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    """Invalidar cache de produtos quando produto é salvo ou deletado"""
    logger.info(f"🔄 [CACHE] Invalidando cache de produtos após mudança em {instance.slug}")
    
    # Invalidar cache de produtos (all e active)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:*")
    
    # Invalidar cache de produtos disponíveis (pode ter mudado)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:available:*")


@receiver(post_save, sender=Plan)
@receiver(post_delete, sender=Plan)
def invalidate_plan_cache(sender, instance, **kwargs):
    """Invalidar cache de planos quando plano é salvo ou deletado"""
    logger.info(f"🔄 [CACHE] Invalidando cache de planos após mudança em {instance.slug}")
    
    # Invalidar cache de planos (all e active)
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PLAN}:*")


@receiver(post_save, sender=TenantProduct)
@receiver(post_delete, sender=TenantProduct)
def invalidate_tenant_product_cache(sender, instance, **kwargs):
    """Invalidar cache de produtos do tenant quando tenant_product é salvo ou deletado"""
    # ✅ CORREÇÃO: Verificar se tenant existe antes de acessar (pode ser null temporariamente)
    if not instance.tenant:
        logger.debug(f"🔄 [CACHE] TenantProduct sem tenant, pulando invalidação de cache")
        return
    
    logger.info(f"🔄 [CACHE] Invalidando cache de produtos do tenant {instance.tenant.id}")
    
    # Invalidar cache de produtos do tenant específico
    cache_key = CacheManager.make_key(
        CacheManager.PREFIX_TENANT_PRODUCT,
        tenant_id=instance.tenant.id
    )
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT_PRODUCT}:*")
    
    # Invalidar cache de produtos disponíveis para este tenant
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:available:tenant_id:{instance.tenant.id}")
    
    # Invalidar cache de resumo de billing do tenant
    CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT}:billing_summary:tenant_id:{instance.tenant.id}")

