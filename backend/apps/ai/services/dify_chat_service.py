"""
Serviço de takeover Dify: encaminha mensagens do cliente para o agente Dify ativo
e envia a resposta de volta via WhatsApp.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from django.db import connection as _conn

logger = logging.getLogger(__name__)


@dataclass
class DifyMessageStub:
    """
    Representação mínima de uma mensagem usada pelo serviço de takeover.
    Substituir o objeto anônimo type('_M', ...) por um dataclass explícito
    torna o contrato entre webhooks.py e dify_chat_service.py claro e seguro.
    """
    content: str


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
    """
    Retorna o estado de takeover Dify ativo para a conversa, ou None.
    Usa SELECT FOR UPDATE para serializar o acesso entre múltiplos workers/threads,
    substituindo o lock in-memory (que não funciona entre processos gunicorn).
    O caller deve envolver esta chamada em transaction.atomic().
    """
    try:
        with _conn.cursor() as cur:
            cur.execute(
                "SELECT id, catalog_id, dify_conversation_id "
                "FROM ai_dify_conversation_state "
                "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active' "
                "LIMIT 1 FOR UPDATE SKIP LOCKED",
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


def _update_dify_conversation_id(state_id: str, dify_conversation_id: str) -> bool:
    """
    Persiste o dify_conversation_id para manter continuidade da sessão.
    Retorna True se bem-sucedido.
    """
    try:
        with _conn.cursor() as cur:
            cur.execute(
                "UPDATE ai_dify_conversation_state "
                "SET dify_conversation_id = %s, updated_at = now() "
                "WHERE id = %s",
                [dify_conversation_id, state_id]
            )
        return True
    except Exception as exc:
        logger.error(
            "❌ [DIFY] Falha ao persistir dify_conversation_id para state %s: %s — "
            "contexto da sessão será perdido na próxima mensagem.",
            state_id, exc
        )
        return False


def maybe_handle_dify_takeover(
    tenant,
    conversation,
    message: DifyMessageStub,
    wa_instance=None,
) -> bool:
    """
    Verifica se há um agente Dify ativo para a conversa e, se houver,
    encaminha a mensagem do cliente ao Dify e envia a resposta ao WhatsApp.

    Usa SELECT FOR UPDATE via transaction.atomic() para serializar execuções
    por conversation_id entre múltiplos workers (substitui lock in-memory).

    Retorna True se o takeover foi tratado, False caso contrário.
    """
    from django.db import transaction

    conv_id = str(conversation.id)
    tenant_id = str(tenant.id)

    # Texto da mensagem
    msg_content = (message.content or '').strip()
    if not msg_content:
        return False

    # EC-B06: validar contact_phone ANTES de qualquer chamada externa
    contact_phone = (getattr(conversation, 'contact_phone', None) or '').strip()
    if not contact_phone:
        logger.warning(
            "Dify takeover: sem telefone do contato para conversa %s — abortando antes do Dify",
            conv_id
        )
        return False

    # Usar transaction.atomic() + SELECT FOR UPDATE para serializar entre workers (C1/C7)
    # Se outro worker já está processando esta conversa, SKIP LOCKED retorna None imediatamente
    with transaction.atomic():
        state = _get_active_dify_state(conv_id, tenant_id)
        if not state:
            return False

        try:
            from apps.ai.models import DifyAppCatalogItem
            agent = DifyAppCatalogItem.objects.get(
                id=state['catalog_id'],
                tenant=tenant,
                is_active=True,
            )
        except Exception as exc:
            logger.warning("Dify takeover: agente não encontrado (%s)", exc)
            return False

        # Base URL extraída via urlparse
        base_url = _extract_dify_base_url(agent.public_url or '')
        if not base_url:
            logger.warning("Dify takeover: public_url inválida para agente %s", agent.id)
            return False

        # Ler a api_key (django-cryptography descriptografa ao acessar o campo)
        api_key = (agent.api_key_encrypted or '').strip()
        if not api_key:
            logger.warning("Dify takeover: api_key vazia para agente %s", agent.id)
            return False

        # EC-B05: resolver instância WA ANTES de chamar o Dify
        # (se não houver instância, abortar sem gastar créditos)
        effective_instance = _resolve_wa_instance(agent, tenant, wa_instance, conversation)
        if not effective_instance:
            logger.warning(
                "Dify takeover: nenhuma instância WA disponível para conversa %s — abortando antes do Dify",
                conv_id
            )
            return False

        # Payload para /v1/chat-messages
        payload: dict = {
            'inputs': {},
            'query': msg_content,
            'response_mode': 'blocking',
            'user': f"sense-{conv_id}",
        }
        if state.get('dify_conversation_id'):
            payload['conversation_id'] = state['dify_conversation_id']

    # Chamada HTTP ao Dify FORA da transaction (evita segurar o lock do banco por 30s)
    dify_answer, new_dify_conv_id = _call_dify_api(base_url, api_key, payload, agent.id)

    if dify_answer is None:
        # Erro na chamada — já logado em _call_dify_api
        return False

    # Persistir conversation_id (nova transaction curta)
    if new_dify_conv_id and new_dify_conv_id != state.get('dify_conversation_id'):
        _update_dify_conversation_id(state['state_id'], new_dify_conv_id)

    if not dify_answer:
        logger.warning(
            "⚠️ [DIFY] Agente %s retornou resposta vazia para conversa %s — "
            "cliente não recebeu resposta. Verifique o fluxo do agente no Dify.",
            agent.dify_app_id, conv_id
        )
        return True  # takeover tratou a mensagem, mas sem resposta ao cliente

    # Enviar resposta via Evolution API
    return _send_wa_reply(effective_instance, contact_phone, dify_answer, agent.dify_app_id, conv_id)


def _resolve_wa_instance(agent, tenant, wa_instance, conversation):
    """Determina a instância WhatsApp a usar para enviar a resposta."""
    try:
        if agent.whatsapp_instance_id:
            from apps.notifications.models import WhatsAppInstance
            inst = WhatsAppInstance.objects.filter(
                id=agent.whatsapp_instance_id, tenant=tenant, is_active=True
            ).first()
            if inst:
                return inst
        if wa_instance:
            return wa_instance
        from apps.chat.instance_resolution import get_effective_wa_instance_for_conversation
        return get_effective_wa_instance_for_conversation(conversation)
    except Exception as exc:
        logger.warning("Dify takeover: erro ao resolver instância (%s)", exc)
    return None


def _call_dify_api(base_url: str, api_key: str, payload: dict, agent_id) -> tuple[str | None, str]:
    """
    Chama o endpoint /v1/chat-messages do Dify.
    Retorna (answer, dify_conversation_id).
    Retorna (None, '') em caso de erro (já logado).
    """
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
                    resp.status_code, agent_id, resp.text[:200]
                )
                return None, ''
            data = resp.json()
            return (data.get('answer') or ''), (data.get('conversation_id') or '')
    except Exception as exc:
        logger.error("Dify takeover: erro na chamada Dify (%s)", exc, exc_info=True)
        return None, ''


def _send_wa_reply(effective_instance, contact_phone: str, message: str, agent_app_id: str, conv_id: str) -> bool:
    """Envia a resposta do Dify via Evolution API."""
    try:
        from apps.notifications.whatsapp_providers.evolution import EvolutionProvider
        provider = EvolutionProvider(effective_instance)
        ok, result = provider.send_text(phone=contact_phone, message=message)
        if not ok:
            logger.error("Dify takeover: falha ao enviar via Evolution: %s", result)
            return False
        logger.info(
            "✅ [DIFY] Resposta enviada na conversa %s (agente %s)",
            conv_id, agent_app_id
        )
        return True
    except Exception as exc:
        logger.error("Dify takeover: erro ao enviar mensagem (%s)", exc, exc_info=True)
        return False
