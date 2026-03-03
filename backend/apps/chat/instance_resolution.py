"""
Resolução de instância WhatsApp para conversas.

Quando um tenant troca de instância (remove uma e conecta outra), conversas antigas
continuam com instance_name da instância removida. Este módulo fornece fallback:
se o tenant tiver apenas uma instância ativa, ela "assume" as conversas órfãs.
"""
import uuid
from django.db.models import Q
from django.core.cache import cache

from apps.notifications.models import WhatsAppInstance

_CACHE_KEY_PREFIX = "effective_wa_conv"
_CACHE_TTL = 60  # 1 minuto: reduz queries em listas sem fixar instância removida por muito tempo


def _get_attr(obj, key, default=None):
    """Suporta model instance ou dict (ex.: values())."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_effective_wa_instance_for_conversation(conversation):
    """
    Retorna a WhatsAppInstance efetiva para a conversa.

    - Se conversation.instance_name bater com alguma instância ativa do tenant, retorna ela.
    - Se não existir instância com esse instance_name mas o tenant tiver exatamente
      uma instância ativa, retorna essa (nova instância "assume" conversas órfãs).
    - Caso contrário retorna None.

    Útil quando o tenant removeu a instância antiga e conectou outra: as conversas
    deixam de "reclamar" da instância de origem e passam a usar a nova.

    Resultado é cacheado por (tenant_id, instance_name) para evitar N+1 em listas.
    """
    tenant_id = _get_attr(conversation, "tenant_id") if conversation else None
    if not tenant_id:
        return None
    inst_name = (_get_attr(conversation, "instance_name") or "").strip()
    cache_key = f"{_CACHE_KEY_PREFIX}:{tenant_id}:{inst_name or '_'}"

    cached_id = cache.get(cache_key)
    if cached_id is not None:
        if cached_id == "":
            return None
        try:
            uuid.UUID(str(cached_id))
        except (ValueError, TypeError, AttributeError):
            cache.delete(cache_key)
        else:
            wa = WhatsAppInstance.objects.filter(
                id=cached_id, tenant_id=tenant_id, is_active=True
            ).first()
            if wa is not None:
                return wa
            cache.delete(cache_key)

    wa = _resolve_effective_wa_instance(tenant_id, inst_name)
    if wa:
        cache.set(cache_key, str(wa.id), _CACHE_TTL)
        return wa
    cache.set(cache_key, "", _CACHE_TTL)
    return None


def _resolve_effective_wa_instance(tenant_id, inst_name):
    """Lógica de resolução sem cache (usada por get_effective_wa_instance_for_conversation)."""
    # 1) Buscar pela instância da conversa
    if inst_name:
        q = Q(instance_name=inst_name) | Q(evolution_instance_name=inst_name)
        if inst_name.isdigit():
            q = q | Q(phone_number_id=inst_name)
        wa = WhatsAppInstance.objects.filter(
            q, tenant_id=tenant_id, is_active=True
        ).first()
        if wa:
            return wa

    # 2) Fallback: tenant com uma única instância ativa → ela assume (uma query só)
    active = list(
        WhatsAppInstance.objects.filter(tenant_id=tenant_id, is_active=True).only(
            "id", "friendly_name", "instance_name", "integration_type"
        )
    )
    if len(active) == 1:
        return active[0]
    return None
