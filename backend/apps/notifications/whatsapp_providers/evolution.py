"""
Provider Evolution API (Baileys). Encapsula chamadas atuais à Evolution.
"""
import logging
import re
import requests
from typing import Tuple, Dict, Any, Optional

from django.conf import settings

from apps.notifications.models import WhatsAppInstance
from .base import WhatsAppSenderBase

logger = logging.getLogger(__name__)


class EvolutionProvider(WhatsAppSenderBase):
    """Provider que usa Evolution API para envio."""

    def __init__(self, instance: WhatsAppInstance):
        if not instance:
            raise ValueError("EvolutionProvider requer instância")
        it = getattr(instance, 'integration_type', None)
        if it and it != WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION:
            raise ValueError("EvolutionProvider requer integration_type=evolution")
        self.instance = instance
        self._base_url = (instance.api_url or '').rstrip('/')
        self._api_key = getattr(settings, 'EVOLUTION_API_KEY', '') or (instance.api_key or '')
        self._instance_name = instance.evolution_api_instance_name or instance.instance_name or ''

    def _headers(self) -> Dict[str, str]:
        return {
            'apikey': self._api_key,
            'Content-Type': 'application/json',
        }

    def _phone_clean(self, phone: str) -> str:
        """Remove sufixo @s.whatsapp.net ou @g.us para número puro (Evolution espera número sem +)."""
        if not phone:
            return ''
        s = phone.strip()
        for suffix in ('@s.whatsapp.net', '@g.us'):
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return s.replace('+', '').strip()

    def send_text(
        self,
        phone: str,
        message: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        number = self._phone_clean(phone)
        if not number:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        logger.info(
            "Enviando texto via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        payload = {
            'number': number,
            'text': (message or '')[:4096],
        }
        if quoted_message_id:
            payload['quoted'] = {
                'key': {
                    'id': quoted_message_id,
                    'remoteJid': f'{number}@s.whatsapp.net',
                },
            }
        endpoint = f"{self._base_url}/message/sendText/{self._instance_name}"
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=10)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            return False, {'error': r.text[:500], 'status_code': r.status_code, 'response': r.text}
        except Exception as e:
            logger.exception("Evolution send_text error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

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
        import requests
        # phone pode ser recipient_value (número ou JID completo @s.whatsapp.net / @g.us)
        recipient = phone.strip() if phone else ''
        if not recipient:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        if mime_type.startswith('image/'):
            mediatype = 'image'
        elif mime_type.startswith('video/'):
            mediatype = 'video'
        else:
            mediatype = 'document'
        payload = {
            'number': recipient,
            'media': media_url,
            'mediatype': mediatype,
            'fileName': filename or 'file',
        }
        if caption:
            payload['caption'] = caption
        if quoted_message_id and kwargs.get('quoted_remote_jid') and kwargs.get('quoted_message_content'):
            payload['options'] = {
                'quoted': {
                    'key': {
                        'remoteJid': kwargs['quoted_remote_jid'],
                        'fromMe': kwargs.get('quoted_from_me', False),
                        'id': quoted_message_id,
                    },
                    'message': {'conversation': (kwargs.get('quoted_message_content') or '')[:100] or '.'},
                }
            }
        endpoint = f"{self._base_url}/message/sendMedia/{self._instance_name}"
        logger.info(
            "Enviando mídia via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=30)
            if r.status_code in (200, 201):
                data = r.json() if r.text else {}
                return True, data
            return False, {'error': r.text[:500], 'status_code': r.status_code, 'response': r.text}
        except Exception as e:
            logger.exception("Evolution send_media error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

    def send_audio_ptt(
        self,
        phone: str,
        audio_url: str,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        import requests
        recipient = phone.strip() if phone else ''
        if not recipient:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        payload = {
            'number': recipient,
            'audio': audio_url,
            'delay': 1200,
            'linkPreview': False,
        }
        if quoted_message_id and kwargs.get('quoted_remote_jid') and kwargs.get('quoted_message_content'):
            payload['options'] = {
                'quoted': {
                    'key': {
                        'remoteJid': kwargs['quoted_remote_jid'],
                        'fromMe': kwargs.get('quoted_from_me', False),
                        'id': quoted_message_id,
                    },
                    'message': {'conversation': (kwargs.get('quoted_message_content') or 'Áudio')[:100]},
                }
            }
        endpoint = f"{self._base_url}/message/sendWhatsAppAudio/{self._instance_name}"
        logger.info(
            "Enviando áudio PTT via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=30)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            if r.status_code == 404:
                # Fallback sendMedia audio
                fb = {
                    'number': recipient,
                    'media': audio_url,
                    'mediatype': 'audio',
                    'fileName': 'audio',
                    'linkPreview': False,
                }
                r2 = requests.post(
                    f"{self._base_url}/message/sendMedia/{self._instance_name}",
                    json=fb,
                    headers=self._headers(),
                    timeout=30,
                )
                if r2.status_code in (200, 201):
                    return True, (r2.json() if r2.text else {})
                return False, {'error': r2.text[:500], 'status_code': r2.status_code}
            return False, {'error': r.text[:500], 'status_code': r.status_code}
        except Exception as e:
            logger.exception("Evolution send_audio_ptt error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

    def send_reaction(
        self,
        phone: str,
        message_id: str,
        emoji: str,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        import requests
        remote_jid = kwargs.get('remote_jid') or (phone if phone and '@' in phone else f"{self._phone_clean(phone) or phone}@s.whatsapp.net")
        payload = {
            'number': remote_jid,
            'key': {'id': message_id, 'remoteJid': remote_jid},
            'reaction': emoji or '',
        }
        endpoint = f"{self._base_url}/message/sendReaction/{self._instance_name}"
        logger.info(
            "Enviando reação via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=10)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            return False, {'error': r.text[:500], 'status_code': r.status_code}
        except Exception as e:
            logger.exception("Evolution send_reaction error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

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
        import requests
        recipient = phone.strip() if phone else ''
        if not recipient:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        payload = {
            'number': recipient,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'name': (name or 'Localização')[:255],
            'address': (address or '')[:500],
        }
        if quoted_message_id and kwargs.get('quoted_remote_jid') and kwargs.get('quoted_message_content'):
            payload['quoted'] = {
                'key': {'id': quoted_message_id},
                'message': {'conversation': (kwargs.get('quoted_message_content') or '')[:100] or '.'},
            }
        endpoint = f"{self._base_url}/message/sendLocation/{self._instance_name}"
        logger.info(
            "Enviando localização via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=15)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            return False, {'error': r.text[:500], 'status_code': r.status_code}
        except Exception as e:
            logger.exception("Evolution send_location error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

    def send_contact(
        self,
        phone: str,
        contacts: list,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem de contato (vCard) via Evolution sendContact.
        contacts: lista de dicts com fullName, wuid, phoneNumber (ou raw: display_name/name, phone).

        IMPORTANTE: request usa chave `contact` (array); `contactMessage`
        aparece apenas na resposta da Evolution.
        v1: envia apenas o primeiro contato.
        """
        from apps.chat.utils.contact_message import normalize_contact_for_provider

        number = self._phone_clean(phone)
        if not number:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        if not contacts or not isinstance(contacts, list):
            return False, {'error': 'lista de contatos vazia', 'error_code': 'INVALID_CONTACTS'}
        normalized = []
        for c in contacts:
            if isinstance(c, dict) and (c.get('fullName') and c.get('wuid') and c.get('phoneNumber')):
                full_name = (c.get('fullName') or '').strip() or 'Contato'
                 # Evolution espera wuid como JID (<digits>@s.whatsapp.net)
                wuid = str(c.get('wuid', '')).strip()
                if wuid and '@' not in wuid:
                    wuid = f'{wuid}@s.whatsapp.net'
                normalized.append({
                    'fullName': full_name[:255],
                    'wuid': wuid,
                    'phoneNumber': str(c.get('phoneNumber', '')).strip(),
                })
            else:
                one = normalize_contact_for_provider(c)
                if one:
                    # Helper retorna wuid como dígitos; Evolution quer JID.
                    wuid = str(one.get('wuid', '')).strip()
                    if wuid and '@' not in wuid:
                        one['wuid'] = f'{wuid}@s.whatsapp.net'
                    normalized.append(one)
        if not normalized:
            return False, {'error': 'nenhum contato válido', 'error_code': 'INVALID_CONTACTS'}
        contact_message = [normalized[0]]
        payload = {
            'number': number,
            # Evolution v2: request usa `contact` (array de contatos)
            'contact': contact_message,
        }
        if quoted_message_id and kwargs.get('quoted_remote_jid'):
            payload['quoted'] = {
                'key': {
                    'id': quoted_message_id,
                    'remoteJid': kwargs.get('quoted_remote_jid'),
                },
            }
        endpoint = f"{self._base_url}/message/sendContact/{self._instance_name}"
        logger.info(
            "Enviando contato via Evolution (provider=evolution instance_id=%s)",
            str(self.instance.id),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=15)
            if r.status_code in (200, 201):
                try:
                    data = r.json() if r.text else {}
                except Exception:
                    return False, {
                        'error': (r.text or '')[:500],
                        'status_code': r.status_code,
                        'error_code': 'INVALID_RESPONSE',
                    }
                return True, data
            return False, {'error': (r.text or '')[:500], 'status_code': r.status_code, 'response': r.text}
        except Exception as e:
            logger.exception("Evolution send_contact error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

    def send_interactive_reply_buttons(
        self,
        phone: str,
        body_text: str,
        buttons: list,
        quoted_message_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Envia mensagem com botões de resposta (reply buttons) via Evolution sendButtons.
        Assim o destinatário vê os botões no WhatsApp.
        buttons: list of dicts com 'id' e 'title' (ex.: [{'id': '1', 'title': 'Sim'}, ...]).
        """
        # Evolution docs para sendButtons indicam `number` no formato remoteJid.
        # Para conversa individual, garantimos "<digits>@s.whatsapp.net".
        raw_phone = (phone or '').strip()
        if raw_phone.endswith('@g.us'):
            return False, {'error': 'botões não suportados em grupos', 'error_code': 'GROUP_NOT_SUPPORTED'}

        number_digits = self._phone_clean(raw_phone)
        if not number_digits:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        remote_jid = raw_phone if ('@' in raw_phone) else f'{number_digits}@s.whatsapp.net'
        if not buttons or not isinstance(buttons, list) or len(buttons) > 3:
            return False, {'error': 'buttons inválido (lista com 1 a 3 itens)', 'error_code': 'INVALID_BUTTONS'}
        action_buttons = []
        for b in buttons[:3]:
            if not isinstance(b, dict):
                continue
            bid = (b.get('id') or '').strip() or str(len(action_buttons))
            title = (b.get('title') or b.get('displayText') or '').strip() or bid
            if isinstance(title, bytes):
                title = title.decode('utf-8', errors='replace').strip()
            action_buttons.append({
                'id': str(bid)[:100],
                'displayText': (title or ' ')[:100],
                'title': 'reply',
            })
        if len(action_buttons) < 1:
            return False, {'error': 'nenhum botão válido', 'error_code': 'INVALID_BUTTONS'}
        body = (body_text or ' ').strip().replace('\x00', '')[:1024] or 'Mensagem'
        payload = {
            'number': remote_jid,
            'title': (body[:50] if len(body) > 50 else body) or 'Mensagem',
            'description': body,
            'footer': '',
            'buttons': action_buttons,
        }
        if quoted_message_id:
            payload['quoted'] = {
                'key': {
                    'id': quoted_message_id,
                    'remoteJid': remote_jid,
                },
            }
        endpoint = f"{self._base_url}/message/sendButtons/{self._instance_name}"
        logger.info(
            "Enviando botões via Evolution (provider=evolution instance_id=%s) %s botões",
            str(self.instance.id),
            len(action_buttons),
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=15)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            return False, {'error': r.text[:500], 'status_code': r.status_code, 'response': r.text}
        except Exception as e:
            logger.exception("Evolution send_interactive_reply_buttons error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}

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
        Envia mensagem interativa tipo lista via Evolution sendList.
        Evolution API: POST /message/sendList/{instance}, body no nível raiz:
        number, title, description, buttonText, footerText, sections (array de {title, rows}).
        Mapeia header_text -> title; body_text -> description; id -> rowId.
        """
        raw_phone = (phone or '').strip()
        if raw_phone.endswith('@g.us'):
            return False, {'error': 'lista não suportada em grupos', 'error_code': 'GROUP_NOT_SUPPORTED'}
        number_digits = self._phone_clean(raw_phone)
        if not number_digits:
            return False, {'error': 'phone vazio', 'error_code': 'INVALID_PHONE'}
        remote_jid = raw_phone if ('@' in raw_phone) else f'{number_digits}@s.whatsapp.net'

        body_clean = (body_text or '').strip().replace('\x00', '')
        if not body_clean:
            return False, {'error': 'Corpo da mensagem (body_text) obrigatório', 'error_code': 'INVALID_BODY'}
        if len(body_clean) > 1024:
            return False, {'error': 'body_text deve ter no máximo 1024 caracteres', 'error_code': 'INVALID_BODY'}
        btn_clean = (button_text or '').strip().replace('\x00', '')[:20]
        if not btn_clean:
            return False, {'error': 'Texto do botão (button_text) obrigatório', 'error_code': 'INVALID_BUTTON'}
        if len((button_text or '').strip()) > 20:
            return False, {'error': 'button_text deve ter no máximo 20 caracteres', 'error_code': 'INVALID_BUTTON'}
        if header_text is not None and len((header_text or '').strip()) > 60:
            return False, {'error': 'header_text deve ter no máximo 60 caracteres', 'error_code': 'INVALID_HEADER'}
        if footer_text is not None and len((footer_text or '').strip()) > 60:
            return False, {'error': 'footer_text deve ter no máximo 60 caracteres', 'error_code': 'INVALID_FOOTER'}
        if not sections or not isinstance(sections, list):
            return False, {'error': 'Pelo menos uma seção é obrigatória', 'error_code': 'INVALID_SECTIONS'}

        list_sections = []
        all_row_ids = set()
        total_rows = 0
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            sec_title = (sec.get('title') or '').strip()[:24]
            if len((sec.get('title') or '').strip()) > 24:
                return False, {'error': 'section.title deve ter no máximo 24 caracteres', 'error_code': 'INVALID_SECTION_TITLE'}
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
                row_id = (re.sub(r'[^a-zA-Z0-9_-]', '', raw_id))[:100] or str(total_rows)
                row_title = (r.get('title') or '').strip()
                if not row_title:
                    return False, {'error': 'Cada opção deve ter um título (não vazio)', 'error_code': 'INVALID_ROW_TITLE'}
                if len(row_title) > 24:
                    return False, {'error': 'row.title deve ter no máximo 24 caracteres', 'error_code': 'INVALID_ROW_TITLE'}
                row_desc = (r.get('description') or '').strip()[:72]
                if row_id in all_row_ids:
                    return False, {'error': 'IDs de opções devem ser únicos em todas as seções', 'error_code': 'INVALID_ROW_IDS'}
                all_row_ids.add(row_id)
                row_obj = {'rowId': row_id, 'title': row_title[:24]}
                if row_desc:
                    row_obj['description'] = row_desc
                rows.append(row_obj)
                total_rows += 1
            if not rows:
                return False, {'error': 'Cada seção deve ter pelo menos uma opção (row)', 'error_code': 'INVALID_SECTIONS'}
            list_sections.append({'title': sec_title or 'Seção', 'rows': rows})
        if total_rows < 1:
            return False, {'error': 'Pelo menos uma opção (row) no total', 'error_code': 'INVALID_SECTIONS'}

        # Evolution API: body at ROOT (no listMessage wrapper). Some versions expect "sections", others "values".
        title_evolution = (header_text or '').strip()[:60] if header_text else (body_clean[:60] if len(body_clean) > 60 else body_clean)
        footer_clean = (footer_text or '').strip()[:60]
        if not footer_clean:
            footer_clean = ' '  # API requires footerText present; empty string can cause 400
        payload = {
            'number': remote_jid,
            'title': title_evolution or 'Mensagem',
            'description': body_clean[:1024],
            'buttonText': btn_clean,
            'footerText': footer_clean,
            'sections': list_sections,  # Evolution instances may expect "sections" or "values"; "sections" works with current deploy
        }
        if quoted_message_id:
            payload['quoted'] = {
                'key': {
                    'id': quoted_message_id,
                    'remoteJid': remote_jid,
                },
            }
        endpoint = f"{self._base_url}/message/sendList/{self._instance_name}"
        logger.info(
            "Enviando lista via Evolution (provider=evolution instance_id=%s) sections=%s rows=%s",
            str(self.instance.id),
            len(list_sections),
            total_rows,
        )
        try:
            r = requests.post(endpoint, json=payload, headers=self._headers(), timeout=15)
            if r.status_code in (200, 201):
                return True, (r.json() if r.text else {})
            return False, {'error': (r.text or '')[:500], 'status_code': r.status_code, 'response': r.text}
        except Exception as e:
            logger.exception("Evolution send_interactive_list error: %s", e)
            return False, {'error': str(e), 'error_code': 'EXCEPTION'}
