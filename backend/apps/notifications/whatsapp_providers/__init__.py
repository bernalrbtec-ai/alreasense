"""
Providers de envio WhatsApp: Evolution (QR) e Meta Cloud API.
Use get_sender(instance) para obter o provider correto conforme integration_type.
"""
from .base import WhatsAppSenderBase
from .evolution import EvolutionProvider
from .meta_cloud import MetaCloudProvider
from .get_sender import get_sender

__all__ = [
    'WhatsAppSenderBase',
    'EvolutionProvider',
    'MetaCloudProvider',
    'get_sender',
]
