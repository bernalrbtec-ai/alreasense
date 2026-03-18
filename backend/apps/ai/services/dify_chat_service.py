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


_DIFY_VAR_RESOLVERS: dict = {
    '{{contact_name}}': lambda conv: getattr(conv, 'contact_name', '') or '',
    '{{contact_phone}}': lambda conv: getattr(conv, 'contact_phone', '') or '',
    '{{conversation_id}}': lambda conv: str(conv.id),
    '{{department_name}}': lambda conv: (
        getattr(conv, 'department_name', '') or
        (getattr(conv, 'department', None) and getattr(conv.department, 'name', '')) or ''
    ),
}


def _resolve_inputs(raw_inputs: dict, conversation) -> dict:
    """
    Substitui variáveis dinâmicas nos valores de raw_inputs usando os dados da conversation.
    Suporta múltiplos placeholders no mesmo valor de string.
    Valores não-string são passados sem modificação.
    Ignora raw_inputs que não seja dict (proteção contra dados corrompidos).
    """
    if not raw_inputs or not isinstance(raw_inputs, dict):
        return {}
    import json as _json
    resolved = {}
    for key, value in raw_inputs.items():
        if not isinstance(value, str):
            # Dify espera strings em todos os campos de input.
            # Tipos compostos (list, dict) são serializados como JSON para não gerar
            # sintaxe Python (ex: "['a', 'b']" em vez de '["a", "b"]').
            if isinstance(value, (list, dict)):
                try:
                    resolved[key] = _json.dumps(value, ensure_ascii=False)
                except (TypeError, ValueError):
                    resolved[key] = str(value)
            else:
                resolved[key] = str(value) if value is not None else ''
            continue
        result = value
        for placeholder, resolver in _DIFY_VAR_RESOLVERS.items():
            if placeholder in result:
                try:
                    result = result.replace(placeholder, str(resolver(conversation)))
                except Exception as exc:
                    logger.warning(
                        "_resolve_inputs: erro ao resolver '%s' para conversa %s: %s",
                        placeholder, getattr(conversation, 'id', '?'), exc
                    )
                    result = result.replace(placeholder, '')
        resolved[key] = result
    return resolved


def _get_audio_transcription(message_id: str, wait_secs: int = 15) -> str:
    """
    Aguarda e retorna a transcrição de áudio de um MessageAttachment.

    Faz polling no banco por até wait_secs segundos, necessário porque:
    - O MessageAttachment é criado por media_tasks.py em thread separada (download S3)
    - A transcrição é disparada só após o download estar completo
    - O N8N/Whisper pode levar vários segundos para responder

    Retorna '' nos seguintes casos (sem esperar o timeout completo quando possível):
    - Attachment existe com processing_status em ('completed','failed','skipped') sem transcrição
      → transcrição desabilitada, falhou ou foi pulada pelo tenant
    - Timeout esgotado sem resultado
    - Qualquer exceção de banco (não deve bloquear o fluxo)

    Nota: NÃO filtra por media_type porque o campo está em metadata (JSONField), não em coluna
    separada. O filtro apenas por message_id é suficiente — esta função só é chamada quando
    _is_audio=True nos webhooks, garantindo que só chegam mensagens de áudio.
    """
    import time
    try:
        from apps.chat.models import MessageAttachment
    except ImportError:
        logger.warning("_get_audio_transcription: não foi possível importar MessageAttachment")
        return ''

    if not message_id:
        return ''

    # Estados terminais: quando o processing_status chegar a um desses valores sem transcrição,
    # não há motivo para continuar o polling — a transcrição não vai aparecer.
    _TERMINAL_STATUSES = {'completed', 'failed', 'skipped', 'error'}

    deadline = time.monotonic() + wait_secs
    attachment_seen = False  # rastreia se attachment já apareceu no banco

    while time.monotonic() < deadline:
        try:
            att = MessageAttachment.objects.filter(
                message_id=message_id,
            ).only('transcription', 'processing_status').first()
        except Exception as exc:
            logger.warning(
                "_get_audio_transcription: erro ao buscar attachment (message_id=%s): %s",
                message_id, exc
            )
            return ''

        if att is not None:
            attachment_seen = True
            if att.transcription and att.transcription.strip():
                logger.info(
                    "_get_audio_transcription: transcrição obtida (message_id=%s len=%s)",
                    message_id, len(att.transcription)
                )
                return att.transcription.strip()
            # Status terminal sem transcrição → não vai mudar, sair imediatamente
            ps = getattr(att, 'processing_status', '') or ''
            if ps in _TERMINAL_STATUSES:
                logger.info(
                    "_get_audio_transcription: status terminal '%s' sem transcrição "
                    "(desabilitada ou falhou). message_id=%s",
                    ps, message_id
                )
                return ''

        time.sleep(1.5)

    if attachment_seen:
        logger.warning(
            "_get_audio_transcription: timeout (%ss) — attachment encontrado mas sem transcrição. "
            "message_id=%s",
            wait_secs, message_id
        )
    else:
        logger.warning(
            "_get_audio_transcription: timeout (%ss) — attachment nunca criado. "
            "Download provavelmente falhou. message_id=%s",
            wait_secs, message_id
        )
    return ''


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

    Usa SELECT FOR UPDATE SKIP LOCKED:
    - Se a linha existe e não está locked → retorna o estado (processamento normal)
    - Se a linha existe mas está locked por outro worker → retorna None com log de aviso
      (mensagem descartada — o outro worker já está respondendo)
    - Se não há linha ativa → retorna None silenciosamente

    O caller deve envolver esta chamada em transaction.atomic().
    """
    try:
        with _conn.cursor() as cur:
            # Caminho principal: tentar adquirir o lock diretamente em uma única query.
            # Elimina a race condition do SELECT duplo anterior: entre o SELECT de existência
            # e o SELECT FOR UPDATE, a linha poderia ser deletada (stop-dify-agent), causando
            # falso log "mensagem descartada por outro worker".
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
            # Lock não obtido ou linha não existe — segundo SELECT apenas para log de diagnóstico.
            # Inconsistência momentânea aqui é aceitável (só afeta o nível do log, não o comportamento).
            cur.execute(
                "SELECT 1 FROM ai_dify_conversation_state "
                "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active' LIMIT 1",
                [str(conversation_id), str(tenant_id)]
            )
            if cur.fetchone():
                logger.warning(
                    "⚡ [DIFY] Conversa %s já está sendo processada por outro worker — "
                    "mensagem descartada para evitar resposta duplicada.",
                    conversation_id
                )
            # else: sem agente ativo — silencioso (return None abaixo)
    except Exception as exc:
        logger.error(
            "❌ [DIFY] _get_active_dify_state erro de banco para conversa %s: %s",
            conversation_id, exc, exc_info=True
        )
    return None


def _update_dify_conversation_id(state_id: str, dify_conversation_id: str, tenant_id: str) -> bool:
    """
    Persiste o dify_conversation_id para manter continuidade da sessão.
    Filtra por tenant_id além de state_id para garantir isolamento entre tenants.
    Retorna True se bem-sucedido.
    """
    from django.db import transaction
    try:
        # C2: transaction.atomic() garante commit explícito
        # Isolamento: WHERE id AND tenant_id evita que um state_id de outro tenant seja atualizado
        with transaction.atomic(), _conn.cursor() as cur:
            cur.execute(
                "UPDATE ai_dify_conversation_state "
                "SET dify_conversation_id = %s, updated_at = now() "
                "WHERE id = %s AND tenant_id = %s",
                [dify_conversation_id, state_id, tenant_id]
            )
            if cur.rowcount == 0:
                logger.warning(
                    "⚠️ [DIFY] _update_dify_conversation_id: nenhuma linha atualizada "
                    "(state_id=%s tenant=%s) — estado pode ter sido removido entre as fases.",
                    state_id, tenant_id
                )
                return False
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

    Fluxo de execução (otimizado para minimizar tempo de lock):
    1. Validações rápidas (sem I/O)
    2. transaction.atomic() + SELECT FOR UPDATE SKIP LOCKED → obtém state_id + catalog_id
       O lock é liberado IMEDIATAMENTE após sair do bloco (apenas leitura do estado)
    3. Fora do lock: busca agente ORM + resolve instância WA + chama Dify HTTP
    4. Persiste dify_conversation_id em transaction curta separada

    Retorna True se o takeover foi tratado, False caso contrário.
    """
    from django.db import transaction

    conv_id = str(conversation.id)
    tenant_id = str(tenant.id)

    logger.info("🤖 [DIFY] maybe_handle_dify_takeover → conversa=%s tenant=%s", conv_id, tenant_id)

    # Validações rápidas antes de qualquer I/O
    msg_content = str(message.content or '').strip()
    if not msg_content:
        logger.info("🤖 [DIFY] Mensagem vazia — ignorando conversa=%s", conv_id)
        return False

    # EC-B06: validar contact_phone ANTES de qualquer chamada externa
    contact_phone = (getattr(conversation, 'contact_phone', None) or '').strip()
    if not contact_phone:
        logger.warning(
            "❌ [DIFY] Sem telefone do contato para conversa %s — abortando",
            conv_id
        )
        return False

    # ── Fase 1: lock curto — apenas ler o estado ativo ──────────────────────────
    # SELECT FOR UPDATE SKIP LOCKED serializa entre workers. O bloco é propositalmente
    # mínimo: só busca o state_id e catalog_id, sem ORM adicional nem I/O externo.
    with transaction.atomic():
        state = _get_active_dify_state(conv_id, tenant_id)
        if not state:
            logger.info("🤖 [DIFY] Sem agente ativo para conversa=%s — ignorando", conv_id)
            return False
        # Capturar tudo que precisamos DENTRO do lock antes de sair da transaction
        state_id = state['state_id']
        catalog_id = state['catalog_id']
        prev_dify_conv_id = state.get('dify_conversation_id')

    # ── Fase 2: fora do lock — buscar agente e resolver instância WA ─────────────
    # D1+D2: ORM query e _resolve_wa_instance fora da transaction para não estender o lock
    try:
        from apps.ai.models import DifyAppCatalogItem
        agent = DifyAppCatalogItem.objects.get(
            id=catalog_id,
            tenant=tenant,
            is_active=True,
        )
    except Exception as exc:
        logger.warning("Dify takeover: agente não encontrado (catalog_id=%s): %s", catalog_id, exc, exc_info=True)
        return False

    base_url = _extract_dify_base_url(agent.public_url or '')
    if not base_url:
        logger.warning("Dify takeover: public_url inválida para agente %s", agent.id)
        return False

    api_key = (agent.api_key_encrypted or '').strip()
    if not api_key:
        logger.warning("Dify takeover: api_key vazia para agente %s", agent.id)
        return False

    # EC-B05: resolver instância WA antes de chamar Dify (evita gastar créditos sem destino)
    effective_instance = _resolve_wa_instance(agent, tenant, wa_instance, conversation)
    if not effective_instance:
        logger.warning(
            "Dify takeover: nenhuma instância WA disponível para conversa %s — abortando antes do Dify",
            conv_id
        )
        return False

    # ── Fase 3: chamada HTTP ao Dify ─────────────────────────────────────────────
    resolved = _resolve_inputs(getattr(agent, 'default_inputs', None) or {}, conversation)
    if resolved:
        logger.info("🤖 [DIFY] Inputs resolvidos (%d campos) para conversa=%s", len(resolved), conv_id)
    payload: dict = {
        'inputs': resolved,
        'query': msg_content,
        'response_mode': 'blocking',
        'user': f"sense-{conv_id}",
    }
    if prev_dify_conv_id:
        payload['conversation_id'] = prev_dify_conv_id

    dify_answer, new_dify_conv_id = _call_dify_api(base_url, api_key, payload, agent.id)
    if dify_answer is None:
        return False

    # ── Fase 4: persistir dify_conversation_id (transaction curta) ───────────────
    if new_dify_conv_id and new_dify_conv_id != prev_dify_conv_id:
        _update_dify_conversation_id(state_id, new_dify_conv_id, tenant_id)

    if not dify_answer:
        logger.warning(
            "⚠️ [DIFY] Agente %s retornou resposta vazia para conversa %s — "
            "tentando enviar mensagem de fallback ao cliente.",
            agent.dify_app_id, conv_id
        )
        # Tentar obter mensagem de fallback configurada nas settings do tenant
        fallback_msg = _get_dify_empty_response_fallback(tenant)
        if fallback_msg:
            _send_wa_reply(effective_instance, contact_phone, fallback_msg, agent.dify_app_id, conv_id)
        # Retornar True: a mensagem foi tratada pelo takeover (mesmo sem resposta útil)
        # para que o fluxo normal não processe esta mensagem em paralelo
        return True

    # ── Fase 5: enviar resposta via Evolution API ─────────────────────────────────
    return _send_wa_reply(effective_instance, contact_phone, dify_answer, agent.dify_app_id, conv_id)


def _get_dify_empty_response_fallback(tenant) -> str:
    """
    Retorna a mensagem de fallback quando o Dify retorna resposta vazia.
    Usa o campo `dify_empty_response_fallback` nas DifySettings do tenant, se configurado.
    Fallback padrão do sistema (pode ser customizado por tenant no futuro).
    """
    try:
        from apps.ai.models import DifySettings
        settings_obj = DifySettings.objects.filter(tenant=tenant).first()
        if settings_obj and getattr(settings_obj, 'empty_response_fallback', None):
            return settings_obj.empty_response_fallback.strip()
    except Exception as exc:
        logger.warning("Dify: falha ao buscar fallback de resposta vazia: %s", exc)
    # Sem fallback configurado → não enviar nada (evitar spam de mensagens genéricas)
    return ''


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
            # Instância configurada existe mas está inativa — não usar fallback silencioso
            logger.warning(
                "Dify takeover: instância WA configurada (id=%s) está inativa ou não encontrada "
                "para agente %s — abortando envio.",
                agent.whatsapp_instance_id, getattr(agent, 'id', '?')
            )
            return None
        if wa_instance:
            return wa_instance
        from apps.chat.instance_resolution import get_effective_wa_instance_for_conversation
        return get_effective_wa_instance_for_conversation(conversation)
    except Exception as exc:
        logger.warning("Dify takeover: erro ao resolver instância: %s", exc, exc_info=True)
    return None


def _call_dify_api(base_url: str, api_key: str, payload: dict, agent_id) -> tuple[str | None, str]:
    """
    Chama o endpoint /v1/chat-messages do Dify.
    Retorna (answer, dify_conversation_id).
    Retorna (None, '') em caso de erro (já logado).
    """
    url = f"{base_url}/v1/chat-messages"
    logger.info(
        "🤖 [DIFY] Chamando API → agente=%s url=%s user=%s conv_id=%s api_key_len=%s",
        agent_id, url, payload.get('user'), payload.get('conversation_id', '(nova)'), len(api_key)
    )
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=55.0, write=10.0, pool=5.0)) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
            )
            logger.debug(
                "🤖 [DIFY] Resposta → status=%s agente=%s body_preview=%s",
                resp.status_code, agent_id, resp.text[:300]
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "❌ [DIFY] status %s para agente %s: %s",
                    resp.status_code, agent_id, resp.text[:500]
                )
                return None, ''
            data = resp.json()
            answer = data.get('answer') or ''
            conv_id = data.get('conversation_id') or ''
            logger.info(
                "🤖 [DIFY] answer_len=%s dify_conv_id=%s agente=%s",
                len(answer), conv_id, agent_id
            )
            return answer, conv_id
    except Exception as exc:
        logger.error("❌ [DIFY] Erro na chamada Dify (%s)", exc, exc_info=True)
        return None, ''


def _send_wa_reply(effective_instance, contact_phone: str, message: str, agent_app_id: str, conv_id: str) -> bool:
    """Envia a resposta do Dify via provider correto (Evolution ou Meta Cloud)."""
    integration_type = getattr(effective_instance, 'integration_type', None) or 'evolution'
    logger.info(
        "📤 [DIFY] Enviando resposta → conversa=%s agente=%s instancia=%s provider=%s phone=%s msg_len=%s",
        conv_id, agent_app_id,
        getattr(effective_instance, 'id', '?'),
        integration_type,
        (contact_phone[:4] + '***') if contact_phone and len(contact_phone) >= 4 else '***',
        len(message)
    )
    try:
        from apps.notifications.whatsapp_providers.get_sender import get_sender
        provider = get_sender(effective_instance)
        if not provider:
            logger.error(
                "❌ [DIFY] Provider não disponível para instância %s (integration_type=%s)",
                getattr(effective_instance, 'id', '?'), integration_type
            )
            return False
        ok, result = provider.send_text(phone=contact_phone, message=message)
        if not ok:
            logger.error("❌ [DIFY] Falha ao enviar via %s: %s", integration_type, result)
            return False
        logger.info(
            "✅ [DIFY] Resposta enviada na conversa %s (agente %s via %s)",
            conv_id, agent_app_id, integration_type
        )
        return True
    except Exception as exc:
        logger.error("❌ [DIFY] Erro ao enviar mensagem (%s)", exc, exc_info=True)
        return False
