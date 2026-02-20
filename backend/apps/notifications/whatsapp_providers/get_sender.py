"""
Retorna o provider de envio correto para uma WhatsAppInstance conforme integration_type.
"""
import logging
from typing import Optional

from apps.notifications.models import WhatsAppInstance
from .base import WhatsAppSenderBase
from .evolution import EvolutionProvider
from .meta_cloud import MetaCloudProvider

logger = logging.getLogger(__name__)


def get_sender(instance: Optional[WhatsAppInstance]) -> Optional[WhatsAppSenderBase]:
    """
    Valida campos da instância e retorna o provider conforme integration_type.
    - evolution -> EvolutionProvider (api_url, api_key, instance_name)
    - meta_cloud -> MetaCloudProvider (phone_number_id, access_token)
    Retorna None se instância inválida ou tipo não suportado.
    """
    if not instance:
        return None
    # Tratar integration_type None como Evolution (linhas antigas antes da coluna Meta)
    integration_type = getattr(instance, 'integration_type', None) or WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION
    try:
        if integration_type == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            if not (instance.phone_number_id and instance.access_token):
                logger.warning(
                    "get_sender: instância meta_cloud sem phone_number_id ou access_token (instance_id=%s)",
                    instance.id,
                )
                return None
            logger.debug(
                "get_sender: provider=meta instance_id=%s",
                instance.id,
            )
            return MetaCloudProvider(instance)
        if integration_type == WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION:
            # default ou evolution (aceitar instance_name ou evolution_instance_name)
            api_url = getattr(instance, 'api_url', None)
            name = (getattr(instance, 'instance_name', None) or '').strip() or (getattr(instance, 'evolution_instance_name', None) or '').strip()
            if not (api_url and name):
                logger.warning(
                    "get_sender: instância evolution sem api_url ou instance_name (instance_id=%s)",
                    instance.id,
                )
                return None
            logger.debug(
                "get_sender: provider=evolution instance_id=%s",
                instance.id,
            )
            return EvolutionProvider(instance)
    except ValueError as e:
        logger.warning(
            "get_sender: validação falhou (instance_id=%s integration_type=%s): %s",
            instance.id,
            getattr(instance, "integration_type", None),
            e,
        )
        return None
    return None
