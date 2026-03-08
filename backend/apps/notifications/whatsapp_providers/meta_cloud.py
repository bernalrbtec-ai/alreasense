"""
Provider Meta WhatsApp Cloud API (Graph API v21.0).
Envio via Bearer token; tratar 401/403/429.
"""
import logging
import re
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

    def send_interactive_reply_buttons(
        self,
        phone: str,
        body_text: str,
        buttons: list,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem interativa com reply buttons (até 3) dentro da janela 24h.
        Meta: type=interactive, interactive.type=button.
        """
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        body_clean = (body_text or '').strip().replace('\x00', '')[:1024]
        if not body_clean:
            return False, {'error': 'Corpo da mensagem obrigatório', 'error_code': 'INVALID_BODY'}
        if not buttons or not isinstance(buttons, list):
            return False, {'error': 'Pelo menos um botão é obrigatório', 'error_code': 'INVALID_BUTTONS'}
        if len(buttons) > 3:
            return False, {'error': 'Máximo 3 botões', 'error_code': 'INVALID_BUTTONS'}
        action_buttons = []
        seen_ids = set()
        for b in buttons:
            if not isinstance(b, dict):
                continue
            raw_id = (b.get('id') or '').strip()
            bid = (re.sub(r'[^a-zA-Z0-9_-]', '', raw_id))[:256]  # Meta: id alfanumérico/underscore/hífen, máx 256
            if not bid:
                continue
            title = (b.get('title') or '').strip()[:20]
            if not bid or not title:
                continue
            if bid in seen_ids:
                continue
            seen_ids.add(bid)
            action_buttons.append({'type': 'reply', 'reply': {'id': bid, 'title': title}})
        if len(action_buttons) < 1:
            return False, {'error': 'Pelo menos um botão válido (id + title)', 'error_code': 'INVALID_BUTTONS'}
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': {
                'type': 'button',
                'body': {'text': body_clean},
                'action': {'buttons': action_buttons},
            },
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        logger.info(
            "Meta Cloud API enviando mensagem interativa com %s botões (instance_id=%s)",
            len(action_buttons),
            str(self.instance.id),
        )
        return self._request(payload)

    # Limites Meta para lista interativa (rejeitar se exceder; não truncar)
    LIST_BUTTON_MAX = 20
    LIST_HEADER_FOOTER_MAX = 60
    LIST_SECTION_TITLE_MAX = 24
    LIST_ROW_TITLE_MAX = 24
    LIST_ROW_DESCRIPTION_MAX = 72
    LIST_BODY_MAX = 1024

    def send_interactive_list(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: list,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem interativa tipo lista (até 10 rows no total) dentro da janela 24h.
        Meta: type=interactive, interactive.type=list.
        Rejeita com mensagem clara se algum limite for excedido (não trunca).
        """
        to = self._to_phone(phone)
        if not to:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        body_clean = (body_text or '').strip().replace('\x00', '')
        if not body_clean:
            return False, {'error': 'Corpo da mensagem (body_text) obrigatório', 'error_code': 'INVALID_BODY'}
        if len(body_clean) > self.LIST_BODY_MAX:
            return False, {'error': f'body_text deve ter no máximo {self.LIST_BODY_MAX} caracteres', 'error_code': 'INVALID_BODY'}
        btn_clean = (button_text or '').strip().replace('\x00', '')[:self.LIST_BUTTON_MAX]
        if not btn_clean:
            return False, {'error': 'Texto do botão (button_text) obrigatório', 'error_code': 'INVALID_BUTTON'}
        if len((button_text or '').strip()) > self.LIST_BUTTON_MAX:
            return False, {'error': f'button_text deve ter no máximo {self.LIST_BUTTON_MAX} caracteres', 'error_code': 'INVALID_BUTTON'}
        if header_text is not None and len((header_text or '').strip()) > self.LIST_HEADER_FOOTER_MAX:
            return False, {'error': f'header_text deve ter no máximo {self.LIST_HEADER_FOOTER_MAX} caracteres', 'error_code': 'INVALID_HEADER'}
        if footer_text is not None and len((footer_text or '').strip()) > self.LIST_HEADER_FOOTER_MAX:
            return False, {'error': f'footer_text deve ter no máximo {self.LIST_HEADER_FOOTER_MAX} caracteres', 'error_code': 'INVALID_FOOTER'}
        if not sections or not isinstance(sections, list):
            return False, {'error': 'Pelo menos uma seção é obrigatória', 'error_code': 'INVALID_SECTIONS'}
        action_sections = []
        all_row_ids = set()
        total_rows = 0
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            sec_title = (sec.get('title') or '').strip()[:self.LIST_SECTION_TITLE_MAX]
            if len((sec.get('title') or '').strip()) > self.LIST_SECTION_TITLE_MAX:
                return False, {'error': f'section.title deve ter no máximo {self.LIST_SECTION_TITLE_MAX} caracteres', 'error_code': 'INVALID_SECTION_TITLE'}
            rows_raw = sec.get('rows') or []
            if not isinstance(rows_raw, list):
                continue
            rows = []
            for r in rows_raw:
                if total_rows >= 10:
                    return False, {'error': 'Máximo 10 opções (rows) no total', 'error_code': 'INVALID_ROWS'}
                if not isinstance(r, dict):
                    continue
                raw_id = (r.get('id') or '').strip()
                rid = (re.sub(r'[^a-zA-Z0-9_-]', '', raw_id))[:256] or str(total_rows)
                row_title = (r.get('title') or '').strip()
                if not row_title:
                    return False, {'error': 'Cada opção deve ter um título (não vazio)', 'error_code': 'INVALID_ROW_TITLE'}
                if len(row_title) > self.LIST_ROW_TITLE_MAX:
                    return False, {'error': f'row.title deve ter no máximo {self.LIST_ROW_TITLE_MAX} caracteres', 'error_code': 'INVALID_ROW_TITLE'}
                row_desc = (r.get('description') or '').strip()
                if row_desc and len(row_desc) > self.LIST_ROW_DESCRIPTION_MAX:
                    return False, {'error': f'row.description deve ter no máximo {self.LIST_ROW_DESCRIPTION_MAX} caracteres', 'error_code': 'INVALID_ROW_DESCRIPTION'}
                if rid in all_row_ids:
                    return False, {'error': 'IDs de opções devem ser únicos em todas as seções', 'error_code': 'INVALID_ROW_IDS'}
                all_row_ids.add(rid)
                row_obj = {'id': rid, 'title': row_title[:self.LIST_ROW_TITLE_MAX]}
                if row_desc:
                    row_obj['description'] = row_desc[:self.LIST_ROW_DESCRIPTION_MAX]
                rows.append(row_obj)
                total_rows += 1
            if not rows:
                return False, {'error': 'Cada seção deve ter pelo menos uma opção (row)', 'error_code': 'INVALID_SECTIONS'}
            action_sections.append({'title': sec_title or 'Seção', 'rows': rows})
        if total_rows < 1:
            return False, {'error': 'Pelo menos uma opção (row) no total', 'error_code': 'INVALID_SECTIONS'}
        interactive_payload = {
            'type': 'list',
            'body': {'text': body_clean[:self.LIST_BODY_MAX]},
            'action': {
                'button': btn_clean,
                'sections': action_sections,
            },
        }
        if header_text and (header_text or '').strip():
            interactive_payload['header'] = {'type': 'text', 'text': (header_text or '').strip()[:self.LIST_HEADER_FOOTER_MAX]}
        if footer_text and (footer_text or '').strip():
            interactive_payload['footer'] = {'text': (footer_text or '').strip()[:self.LIST_HEADER_FOOTER_MAX]}
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': to,
            'type': 'interactive',
            'interactive': interactive_payload,
        }
        if quoted_message_id:
            payload['context'] = {'message_id': quoted_message_id}
        logger.info(
            "Meta Cloud API enviando lista interativa (instance_id=%s sections=%s rows=%s)",
            str(self.instance.id),
            len(action_sections),
            total_rows,
        )
        ok, data = self._request(payload)
        if ok:
            logger.info(
                "Meta Cloud API send_interactive_list OK (instance_id=%s)",
                str(self.instance.id),
            )
        else:
            logger.warning(
                "Meta Cloud API send_interactive_list falhou (instance_id=%s): %s",
                str(self.instance.id),
                data.get('error', ''),
            )
        return ok, data

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
