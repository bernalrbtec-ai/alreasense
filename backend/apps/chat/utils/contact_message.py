"""
Helpers para mensagens de contato (vCard) no chat.
Usado ao enviar contato para Evolution/Meta e ao normalizar payload.
"""
import re
from typing import Any, Dict, List, Optional


# Limite seguro para fullName nas APIs (Evolution/Meta)
FULLNAME_MAX_LENGTH = 255

# Caracteres de controle a remover do nome (evitar erro na API)
CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def extract_contacts_list(contact_message: Any) -> List[Dict[str, Any]]:
    """
    Extrai lista de contatos (dicts) a partir do payload contact_message.

    Aceita: lista de contatos, dict com chave 'contacts' (lista) ou dict único como contato.
    Retorna lista vazia se contact_message for None, não list/dict ou formato inválido.
    """
    if contact_message is None:
        return []
    if isinstance(contact_message, list):
        return [c for c in contact_message if isinstance(c, dict)]
    if isinstance(contact_message, dict):
        if 'contacts' in contact_message and isinstance(contact_message['contacts'], list):
            return [c for c in contact_message['contacts'] if isinstance(c, dict)]
        return [contact_message]
    return []


def _sanitize_full_name(name: str) -> str:
    """Remove caracteres de controle e truncar ao limite."""
    if not name or not isinstance(name, str):
        return ''
    s = CONTROL_CHARS_RE.sub('', name).replace('\r', ' ').replace('\n', ' ').strip()
    return s[:FULLNAME_MAX_LENGTH] if len(s) > FULLNAME_MAX_LENGTH else s


def normalize_contact_for_provider(contact: Any) -> Optional[Dict[str, str]]:
    """
    Normaliza um contato (dict) para o formato esperado pelos providers (Evolution/Meta).

    Entrada: item com display_name/name/fullName e phone/phoneNumber.
    Saída: {'fullName': str, 'wuid': str (dígitos sem +), 'phoneNumber': str (E.164)}
    ou None se telefone inválido.

    Opcionais no item: organization, email, url (copiados só se forem string).
    """
    if contact is None or not isinstance(contact, dict):
        return None

    phone_raw = contact.get('phone') or contact.get('phoneNumber')
    if phone_raw is not None and not isinstance(phone_raw, str):
        phone_raw = str(phone_raw).strip()
    if not phone_raw:
        return None

    from apps.notifications.services import normalize_phone
    normalized_phone = normalize_phone(phone_raw)
    if not normalized_phone:
        return None

    wuid = normalized_phone.lstrip('+').replace(' ', '')
    name = (
        (contact.get('fullName') or contact.get('display_name') or contact.get('name'))
        or ''
    )
    if isinstance(name, str):
        full_name = _sanitize_full_name(name.strip()) or 'Contato'
    else:
        full_name = 'Contato'

    result = {
        'fullName': full_name,
        'wuid': wuid,
        'phoneNumber': normalized_phone,
    }
    for key in ('organization', 'email', 'url'):
        val = contact.get(key)
        if isinstance(val, str) and val.strip():
            result[key] = val.strip()[:500]
    return result
