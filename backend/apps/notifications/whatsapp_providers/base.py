"""
Interface base (ABC) para envio de mensagens WhatsApp.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional


class WhatsAppSenderBase(ABC):
    """Interface para envio de texto, mídia, áudio PTT, reação e localização."""

    @abstractmethod
    def send_text(
        self,
        phone: str,
        message: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia mensagem de texto. phone em E.164 ou número Evolution (com @s.whatsapp.net/@g.us)."""
        pass

    @abstractmethod
    def send_media(
        self,
        phone: str,
        media_url: str,
        mime_type: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia mídia (imagem, vídeo, documento)."""
        pass

    @abstractmethod
    def send_audio_ptt(
        self,
        phone: str,
        audio_url: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia áudio como PTT (push-to-talk)."""
        pass

    @abstractmethod
    def send_reaction(
        self,
        phone: str,
        message_id: str,
        emoji: str,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia reação a uma mensagem (emoji)."""
        pass

    @abstractmethod
    def send_location(
        self,
        phone: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia localização."""
        pass

    def send_template(
        self,
        phone: str,
        template_name: str,
        language_code: str = 'pt_BR',
        body_parameters: Optional[list] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem de template (Meta Cloud API: fora da janela 24h).
        Evolution não suporta; subclasses Meta implementam.
        """
        return False, {'error': 'Templates não suportados neste provider', 'error_code': 'NOT_SUPPORTED'}

    def mark_as_read(self, message_id: str, **kwargs: Any) -> Tuple[bool, Dict[str, Any]]:
        """
        Marca mensagem como lida (read receipt).
        Meta Cloud API tem endpoint próprio; Evolution usa markMessageAsRead.
        """
        return False, {'error': 'mark_as_read não suportado neste provider', 'error_code': 'NOT_SUPPORTED'}

    def send_contact(
        self,
        phone: str,
        contacts: list,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem de contato (vCard). Evolution e Meta implementam.
        contacts: lista de dicts com fullName, wuid, phoneNumber (já normalizados).
        """
        return False, {
            'error': 'Envio de contato não suportado por esta instância.',
            'error_code': 'NOT_SUPPORTED',
        }
