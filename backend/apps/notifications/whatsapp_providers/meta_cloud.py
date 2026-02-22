"""
Provider Meta WhatsApp Cloud API (Graph API v21.0).
Envio via Bearer token; tratar 401/403/429.
"""
import logging
import requests
from typing import Tuple, Dict, Any, Optional

from apps.notifications.models import WhatsAppInstance
from .base import WhatsAppSenderBase

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class MetaCloudProvider(WhatsAppSenderBase):
    """Provider que usa Meta Cloud API (Graph API v21.0) para envio."""

    def __init__(self, instance: WhatsAppInstance):
        if not instance or instance.integration_type != WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            raise ValueError("MetaCloudProvider requer integration_type=meta_cloud")
        phone_number_id = (instance.phone_number_id or '').strip()
        access_token = (instance.access_token or '').strip()
        if not phone_number_id or not access_token:
            raise ValueError("MetaCloudProvider requer phone_number_id e access_token")
        self.instance = instance
        self._phone_number_id = phone_number_id
        self._access_token = access_token

    def _to_phone(self, phone: str) -> str:
        """Remove + e sufixos @s.whatsapp.net / @g.us para o campo 'to' da Meta."""
        if not phone:
            return ''
        s = phone.strip()
        for suffix in ('@s.whatsapp.net', '@g.us'):
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return s.replace('+', '').strip()

    def _request(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        url = f"{GRAPH_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {self._access_token}',
            'Content-Type': 'application/json',
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            data = r.json() if r.text else {}
            if r.status_code in (200, 201):
                logger.info(
                    "Meta Cloud API envio OK (provider=meta instance_id=%s)",
                    str(self.instance.id),
                )
                return True, data
            error_msg = data.get('error', {})
            error_code = error_msg.get('code')
            message = error_msg.get('message', r.text[:500])
            logger.warning(
                "Meta Cloud API erro (provider=meta instance_id=%s): %s %s",
                str(self.instance.id),
                r.status_code,
                message,
            )
            if r.status_code in (401, 403):
                return False, {'error': message, 'error_code': f'HTTP_{r.status_code}', 'meta_code': error_code}
            if r.status_code == 429:
                return False, {'error': message, 'error_code': 'RATE_LIMIT', 'meta_code': error_code}
            return False, {'error': message, 'status_code': r.status_code, 'response': data}
        except requests.RequestException as e:
            logger.exception("Meta Cloud API request error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

    def send_text(
        self,
        phone: str,
        message: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        to = self._to_phone(phone)
        if not to:
            logger.warning("Meta send_text: phone vazio instance_id=%s", str(self.instance.id))
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        logger.debug("Meta send_text: instance_id=%s", str(self.instance.id))
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'text',
            'text': {'body': (message or '')[:4096], 'preview_url': False},
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        return self._request(payload)

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
        """
        Envia mídia (imagem, vídeo, documento, áudio) via Graph API.
        Requer que media_url seja uma URL publicamente acessível (a Meta faz GET nela).
        Para URLs internas, use a Media API da Meta (upload do arquivo e envio por id).
        """
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        if mime_type.startswith('image/'):
            msg_type = 'image'
        elif mime_type.startswith('video/'):
            msg_type = 'video'
        elif mime_type.startswith('audio/'):
            msg_type = 'audio'
        else:
            msg_type = 'document'
        body = {msg_type: {'link': media_url}}
        if msg_type == 'document' and filename:
            body[msg_type]['filename'] = filename[:256]
        if caption and msg_type in ('image', 'video', 'document'):
            body[msg_type]['caption'] = caption[:1024]
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': msg_type,
            **body,
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        return self._request(payload)

    def send_audio_ptt(
        self,
        phone: str,
        audio_url: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia áudio (PTT) via Cloud API.
        Nota: envio por 'link' pode ser exibido como "Encaminhado" no cliente.
        Para evitar: fazer upload via Media API e enviar com audio: { "id": media_id }.
        """
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'audio',
            'audio': {'link': audio_url},
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        return self._request(payload)

    def send_reaction(
        self,
        phone: str,
        message_id: str,
        emoji: str,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'reaction',
            'reaction': {'message_id': message_id, 'emoji': emoji or ''},
        }
        return self._request(payload)

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
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'location',
            'location': {
                'latitude': float(latitude),
                'longitude': float(longitude),
                'name': (name or 'Localização')[:255],
                'address': (address or '')[:500],
            },
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        return self._request(payload)

    def send_template(
        self,
        phone: str,
        template_name: str,
        language_code: str = 'pt_BR',
        body_parameters: Optional[list] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Envia mensagem de template (Meta: fora da janela 24h)."""
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        params = body_parameters or []
        components = []
        if params:
            components.append({
                'type': 'body',
                'parameters': [{'type': 'text', 'text': str(p)[:1024]} for p in params],
            })
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'template',
            'template': {
                'name': template_name[:512],
                'language': {'code': (language_code or 'pt_BR')[:10]},
                **({'components': components} if components else {}),
            },
        }
        return self._request(payload)

    def mark_as_read(self, message_id: str, **kwargs: Any) -> Tuple[bool, Dict[str, Any]]:
        """Marca mensagem como lida (read receipt) via Graph API."""
        if not (message_id or '').strip():
            return False, {'error': 'message_id vazio', 'error_code': 'INVALID_MESSAGE_ID'}
        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': message_id.strip(),
        }
        url = f"{GRAPH_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {self._access_token}',
            'Content-Type': 'application/json',
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            data = r.json() if r.text else {}
            if r.status_code in (200, 201):
                logger.info(
                    "Meta Cloud API mark_as_read OK (provider=meta instance_id=%s)",
                    str(self.instance.id),
                )
                return True, data
            err = data.get('error', {})
            msg = err.get('message', r.text or 'Erro desconhecido')
            return False, {'error': msg, 'status_code': r.status_code}
        except requests.RequestException as e:
            logger.exception("Meta Cloud API mark_as_read error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}
