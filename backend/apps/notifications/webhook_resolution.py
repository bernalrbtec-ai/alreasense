"""
Resolução de WhatsAppInstance pelo identificador enviado no webhook (Evolution API).

Usado por chat/webhooks e connections/webhook_views para garantir roteamento
correto multi-tenant: só instance_name e evolution_instance_name (nunca friendly_name),
incluindo UUID com/sem hífens.
"""
from django.db.models import Q

from apps.notifications.models import WhatsAppInstance


def resolve_wa_instance_by_webhook_id(instance_name):
    """
    Resolve WhatsAppInstance pelo valor do campo 'instance' do webhook.

    - Usa apenas instance_name e evolution_instance_name (case-insensitive).
    - Tenta UUID sem hífens se instance_name parecer UUID (evita falha quando
      Evolution envia com hífens e o banco tem sem, ou vice-versa).
    - Não usa friendly_name para evitar rotear para o tenant errado em multi-tenant.

    Retorna WhatsAppInstance ou None. Nunca levanta.
    """
    if instance_name is None:
        return None
    try:
        raw = str(instance_name).strip()
    except (TypeError, ValueError):
        return None
    if not raw:
        return None
    try:
        qs = (
            WhatsAppInstance.objects.select_related('tenant', 'default_department')
            .filter(
                Q(instance_name__iexact=raw) | Q(evolution_instance_name__iexact=raw),
                is_active=True,
            )
            .exclude(status='error')
            .order_by('id')
        )
        inst = qs.first()
        if inst:
            return inst
        if '-' in raw and len(raw) >= 32:
            compact = raw.replace('-', '')
            qs2 = (
                WhatsAppInstance.objects.select_related('tenant', 'default_department')
                .filter(
                    Q(instance_name__iexact=compact) | Q(evolution_instance_name__iexact=compact),
                    is_active=True,
                )
                .exclude(status='error')
                .order_by('id')
            )
            return qs2.first()
    except Exception:
        pass
    return None
