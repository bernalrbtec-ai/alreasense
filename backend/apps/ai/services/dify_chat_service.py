"""
Serviço de takeover Dify: encaminha mensagens do cliente para o agente Dify ativo
e envia a resposta de volta via WhatsApp.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from django.db import connection as _conn

logger = logging.getLogger(__name__)


def _extract_dify_base_url(public_url: str) -> str:
    """
    Extrai a base URL da URL pública do agente Dify.
    Ex: https://dify.domain.com/chat/WjOslUArZI8QkGRn → https://dify.domain.com
    Usa urlparse para garantir robustez independente do path completo.
    """
    parsed = urlparse(public_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f"{parsed.scheme}://{parsed.netloc}"


def _get_active_dify_state(conversation_id: str, tenant_id: str) -> dict | None:
    """Retorna o estado de takeover Dify ativo para a conversa, ou None."""
    try:
        with _conn.cursor() as cur:
            cur.execute(
                "SELECT id, catalog_id, dify_conversation_id "
                "FROM ai_dify_conversation_state "
                "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active' LIMIT 1",
                [str(conversation_id), str(tenant_id)]
            )
            row = cur.fetchone()
            if row:
                return {
                    'state_id': str(row[0]),
                    'catalog_id': str(row[1]),
                    'dify_conversation_id': row[2],
                }
    except Exception as exc:
        logger.warning("_get_active_dify_state error: %s", exc)
    return None


def _update_dify_conversation_id(state_id: str, dify_conversation_id: str) -> None:
    """Persiste o dify_conversation_id para manter continuidade da sessão."""
    try:
        with _conn.cursor() as cur:
            cur.execute(
                "UPDATE ai_dify_conversation_state "
                "SET dify_conversation_id = %s, updated_at = now() "
                "WHERE id = %s",
                [dify_conversation_id, state_id]
            )
    except Exception as exc:
        logger.warning("_update_dify_conversation_id error: %s", exc)


def maybe_handle_dify_takeover(tenant, conversation, message, wa_instance=None) -> bool:
    """
    Verifica se há um agente Dify ativo para a conversa e, se houver,
    encaminha a mensagem do cliente ao Dify e envia a resposta ao WhatsApp.

    Retorna True se o takeover foi tratado, False caso contrário.
    """
    state = _get_active_dify_state(str(conversation.id), str(tenant.id))
    if not state:
        return False

    try:
        from apps.ai.models import DifyAppCatalogItem
        agent = DifyAppCatalogItem.objects.select_related().get(
            id=state['catalog_id'],
            tenant=tenant,
            is_active=True,
        )
    except Exception as exc:
        logger.warning("Dify takeover: agente não encontrado (%s)", exc)
        return False

    # Texto da mensagem
    msg_content = (getattr(message, 'content', '') or '').strip()
    if not msg_content:
        return False

    # Base URL extraída via urlparse (robusto para qualquer estrutura de path)
    base_url = _extract_dify_base_url(agent.public_url or '')
    if not base_url:
        logger.warning("Dify takeover: public_url inválida para agente %s", agent.id)
        return False

    # Ler a api_key (django-cryptography descriptografa ao acessar o campo)
    api_key = (agent.api_key_encrypted or '').strip()
    if not api_key:
        logger.warning("Dify takeover: api_key vazia para agente %s", agent.id)
        return False

    # Payload Dify /v1/chat-messages
    payload = {
        'inputs': {},
        'query': msg_content,
        'response_mode': 'blocking',
        'user': f"sense-{str(conversation.id)}",
    }
    if state.get('dify_conversation_id'):
        payload['conversation_id'] = state['dify_conversation_id']

    dify_answer = None
    new_dify_conv_id = None

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{base_url}/v1/chat-messages",
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "Dify takeover: status %s para agente %s: %s",
                    resp.status_code, agent.id, resp.text[:200]
                )
                return False
            data = resp.json()
            dify_answer = data.get('answer') or ''
            new_dify_conv_id = data.get('conversation_id') or ''
    except Exception as exc:
        logger.error("Dify takeover: erro na chamada Dify (%s)", exc, exc_info=True)
        return False

    # Persistir conversation_id mesmo que resposta seja vazia (mantém sessão)
    if new_dify_conv_id and new_dify_conv_id != state.get('dify_conversation_id'):
        _update_dify_conversation_id(state['state_id'], new_dify_conv_id)

    if not dify_answer:
        logger.info("Dify takeover: resposta vazia do agente %s (conversa %s)", agent.id, conversation.id)
        return True  # takeover tratado, mas sem mensagem para enviar

    # Determinar instância WA para enviar a resposta
    effective_instance = None
    try:
        if agent.whatsapp_instance_id:
            from apps.notifications.models import WhatsAppInstance
            effective_instance = WhatsAppInstance.objects.filter(
                id=agent.whatsapp_instance_id, tenant=tenant, is_active=True
            ).first()
        if not effective_instance and wa_instance:
            effective_instance = wa_instance
        if not effective_instance:
            from apps.chat.instance_resolution import get_effective_wa_instance_for_conversation
            effective_instance = get_effective_wa_instance_for_conversation(conversation)
    except Exception as exc:
        logger.warning("Dify takeover: erro ao resolver instância (%s)", exc)

    if not effective_instance:
        logger.warning("Dify takeover: nenhuma instância WA disponível para conversa %s", conversation.id)
        return False

    # Enviar resposta via Evolution API
    try:
        from apps.notifications.whatsapp_providers.evolution import EvolutionProvider
        provider = EvolutionProvider(effective_instance)
        contact_phone = (getattr(conversation, 'contact_phone', None) or '').strip()
        if not contact_phone:
            logger.warning("Dify takeover: sem telefone do contato para conversa %s", conversation.id)
            return False

        ok, result = provider.send_text(phone=contact_phone, message=dify_answer)
        if not ok:
            logger.error("Dify takeover: falha ao enviar via Evolution: %s", result)
            return False

        logger.info(
            "✅ [DIFY] Resposta enviada na conversa %s (agente %s)",
            conversation.id, agent.dify_app_id
        )
        return True
    except Exception as exc:
        logger.error("Dify takeover: erro ao enviar mensagem (%s)", exc, exc_info=True)
        return False
