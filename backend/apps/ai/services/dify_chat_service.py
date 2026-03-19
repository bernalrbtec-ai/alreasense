"""
Serviço de takeover Dify: encaminha mensagens do cliente para o agente Dify ativo
e envia a resposta de volta via WhatsApp.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
import re
from urllib.parse import urlparse

import httpx

from django.conf import settings
from django.db import connection as _conn

from apps.chat.services.business_hours_service import BusinessHoursService

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
    '{{tenant_name}}': lambda conv: getattr(getattr(conv, 'tenant', None), 'name', '') or '',
    '{{contact_name}}': lambda conv: getattr(conv, 'contact_name', '') or '',
    '{{contact_phone}}': lambda conv: getattr(conv, 'contact_phone', '') or '',
    '{{conversation_id}}': lambda conv: str(conv.id),
    '{{department_name}}': lambda conv: (
        getattr(conv, 'department_name', '') or
        (getattr(conv, 'department', None) and getattr(conv.department, 'name', '')) or ''
    ),
    '{{is_open}}': lambda conv: (
        # Se por algum motivo não houver tenant na conversation, não bloqueamos o fluxo.
        (
            'true' if getattr(conv, 'tenant', None) is None else (
                'true' if BusinessHoursService.is_business_hours(
                    getattr(conv, 'tenant', None),
                    getattr(conv, 'department', None),
                )[0] else 'false'
            )
        )
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
    # Cacheia placeholders para evitar chamadas repetidas (ex: is_open consulta DB).
    var_cache: dict[str, str] = {}
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
                    if placeholder not in var_cache:
                        var_cache[placeholder] = str(resolver(conversation))
                    result = result.replace(placeholder, var_cache[placeholder])
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


def _normalize_phone_for_dify_user(contact_phone: str) -> str:
    """
    Normaliza o telefone para uso no campo `user` do Dify:
    - remove sufixos de WhatsApp (@g.us/@s.whatsapp.net)
    - remove espaços e símbolos, preservando apenas dígitos
    Retorna string curta/estável (máx ~32 chars) para evitar payloads enormes.
    """
    raw = (contact_phone or "").strip()
    if not raw:
        return ""
    raw = raw.replace("@g.us", "").replace("@s.whatsapp.net", "").strip()
    digits = re.sub(r"[^0-9]+", "", raw)
    return digits[:32]


def _normalize_dify_user(tenant_id: str, agent_app_id: str, contact_phone: str) -> str:
    """
    Identificador estável para memória do Dify, isolado por tenant + agente + telefone.
    Ex.: sense:<tenant>:<agent>:<digits>
    """
    tid = (tenant_id or "").strip() or "t"
    aid = (agent_app_id or "").strip() or "a"
    phone = _normalize_phone_for_dify_user(contact_phone) or "p"
    # manter compacto e com charset seguro
    return f"sense:{tid}:{aid}:{phone}"


def _fetch_dify_conversation_for_user(base_url: str, api_key: str, dify_user: str, agent_id) -> str | None:
    """
    Busca a conversa mais recente do Dify para um `user` estável.
    Retorna dify_conversation_id ou None se não houver / em caso de erro.
    """
    if not (base_url and api_key and dify_user):
        return None
    url = f"{base_url}/v1/conversations"
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)) as client:
            resp = client.get(
                url,
                params={"user": dify_user, "limit": 1, "sort_by": "-updated_at"},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                logger.warning(
                    "⚠️ [DIFY] Falha ao buscar conversas por user (status=%s) agente=%s",
                    resp.status_code,
                    agent_id,
                )
                return None
            data = resp.json()
            # Dify costuma retornar {"data":[{...}]} ou lista direta dependendo da versão
            items = None
            if isinstance(data, dict):
                items = data.get("data") if isinstance(data.get("data"), list) else data.get("conversations")
            elif isinstance(data, list):
                items = data
            if not isinstance(items, list) or not items:
                return None
            first = items[0] if isinstance(items[0], dict) else None
            if not first:
                return None
            conv_id = (first.get("id") or first.get("conversation_id") or "").strip()
            return conv_id or None
    except Exception as exc:
        logger.warning("⚠️ [DIFY] Erro ao buscar conversa por user (%s): %s", dify_user, exc)
        return None


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


def _is_dify_auto_start_globally_enabled() -> bool:
    """
    Kill switch global para auto-start Dify.
    Se ausente em settings, assume habilitado para não quebrar comportamento atual.
    """
    return bool(getattr(settings, "DIFY_AUTO_START_ENABLED", True))


def resolve_dify_assignment_for_conversation(tenant, conversation) -> dict | None:
    """
    Resolve o agent Dify aplicável para uma conversa com base em DifyAssignment.

    Prioridade:
    1) scope=department quando conversation.department_id existe
    2) scope=inbox quando conversation.department_id é nulo

    Também valida:
    - Dify habilitado no tenant (DifySettings.enabled)
    - catálogo ativo
    """
    try:
        from apps.ai.models import DifyAssignment, DifySettings
    except Exception as exc:
        logger.warning("⚠️ [DIFY] resolve assignment: models indisponíveis: %s", exc)
        return None

    tenant_id = str(getattr(tenant, "id", "") or "")
    conv_id = str(getattr(conversation, "id", "") or "")
    dept_id = getattr(conversation, "department_id", None)

    if not tenant_id or not conv_id:
        return None

    if not _is_dify_auto_start_globally_enabled():
        logger.info(
            "dify_auto_start_skipped reason=global_flag_disabled tenant=%s conversation=%s",
            tenant_id,
            conv_id,
        )
        return None

    try:
        settings_obj = DifySettings.objects.filter(tenant=tenant).only("enabled").first()
        if not settings_obj or not bool(getattr(settings_obj, "enabled", False)):
            logger.info(
                "dify_auto_start_skipped reason=dify_disabled tenant=%s conversation=%s",
                tenant_id,
                conv_id,
            )
            return None
    except Exception as exc:
        logger.warning("⚠️ [DIFY] resolve assignment: erro lendo DifySettings: %s", exc)
        return None

    try:
        assignment = None
        if dept_id:
            assignment = (
                DifyAssignment.objects.select_related("catalog")
                .filter(
                    tenant=tenant,
                    scope_type=DifyAssignment.SCOPE_DEPARTMENT,
                    scope_id=dept_id,
                    catalog__is_active=True,
                )
                .first()
            )
        else:
            assignment = (
                DifyAssignment.objects.select_related("catalog")
                .filter(
                    tenant=tenant,
                    scope_type=DifyAssignment.SCOPE_INBOX,
                    scope_id__isnull=True,
                    catalog__is_active=True,
                )
                .first()
            )

        if not assignment or not getattr(assignment, "catalog_id", None):
            logger.info(
                "dify_auto_start_skipped reason=no_assignment tenant=%s conversation=%s department=%s",
                tenant_id,
                conv_id,
                str(dept_id) if dept_id else "",
            )
            return None

        display_name = ""
        if getattr(assignment, "catalog", None):
            display_name = (
                getattr(assignment.catalog, "display_name", "")
                or getattr(assignment.catalog, "dify_app_id", "")
                or ""
            ).strip()

        return {
            "catalog_id": str(assignment.catalog_id),
            "display_name": display_name or "Agente IA",
            "scope_type": assignment.scope_type,
            "scope_id": str(assignment.scope_id) if assignment.scope_id else None,
        }
    except Exception as exc:
        logger.warning("⚠️ [DIFY] resolve assignment: erro ao buscar vínculo: %s", exc, exc_info=True)
        return None


def ensure_active_dify_state_for_conversation(
    tenant,
    conversation,
    *,
    started_by_user_id=None,
    assignment: dict | None = None,
) -> dict | None:
    """
    Garante estado ativo em ai_dify_conversation_state para uma conversa.

    Regras:
    - Se já existe estado ativo, NÃO sobrescreve catálogo.
    - Se não existe ativo e há assignment válido, faz UPSERT idempotente.
    - Retorna metadata do estado ativo final.
    """
    from django.db import transaction

    tenant_id = str(getattr(tenant, "id", "") or "")
    conv_id = str(getattr(conversation, "id", "") or "")
    if not tenant_id or not conv_id:
        return None

    if assignment is None:
        assignment = resolve_dify_assignment_for_conversation(tenant, conversation)
    if not assignment:
        return None

    catalog_id = str(assignment.get("catalog_id") or "").strip()
    if not catalog_id:
        return None

    try:
        with transaction.atomic(), _conn.cursor() as cur:
            cur.execute(
                "SELECT catalog_id, status FROM ai_dify_conversation_state "
                "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active' LIMIT 1",
                [conv_id, tenant_id],
            )
            row = cur.fetchone()
            if row:
                return {
                    "activated": False,
                    "already_active": True,
                    "catalog_id": str(row[0]),
                    "status": row[1] or "active",
                    "display_name": assignment.get("display_name") or "Agente IA",
                }

            cur.execute(
                "INSERT INTO ai_dify_conversation_state "
                "(id, tenant_id, conversation_id, catalog_id, status, started_by_user_id, started_at, updated_at) "
                "VALUES (gen_random_uuid(), %s, %s, %s, 'active', %s, now(), now()) "
                "ON CONFLICT (conversation_id) DO UPDATE SET "
                "catalog_id = EXCLUDED.catalog_id, status = 'active', started_by_user_id = EXCLUDED.started_by_user_id, "
                "updated_at = now(), dify_conversation_id = NULL "
                "WHERE ai_dify_conversation_state.status <> 'active' "
                "RETURNING catalog_id, status",
                [tenant_id, conv_id, catalog_id, started_by_user_id],
            )
            upsert_row = cur.fetchone()

            if not upsert_row:
                cur.execute(
                    "SELECT catalog_id, status FROM ai_dify_conversation_state "
                    "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active' LIMIT 1",
                    [conv_id, tenant_id],
                )
                final_row = cur.fetchone()
                if final_row:
                    return {
                        "activated": False,
                        "already_active": True,
                        "catalog_id": str(final_row[0]),
                        "status": final_row[1] or "active",
                        "display_name": assignment.get("display_name") or "Agente IA",
                    }
                return None
    except Exception as exc:
        logger.error(
            "❌ [DIFY] ensure active state falhou tenant=%s conversation=%s: %s",
            tenant_id,
            conv_id,
            exc,
            exc_info=True,
        )
        return None

    try:
        from apps.chat.utils.websocket import broadcast_to_tenant

        broadcast_to_tenant(
            tenant_id=tenant_id,
            event_type="dify_agent_state_changed",
            data={
                "conversation_id": conv_id,
                "status": "active",
                "catalog_id": catalog_id,
                "display_name": assignment.get("display_name") or "Agente IA",
            },
        )
    except Exception as ws_exc:
        logger.warning(
            "⚠️ [DIFY] Broadcast auto-start falhou (não crítico) conv=%s: %s",
            conv_id,
            ws_exc,
        )

    return {
        "activated": True,
        "already_active": False,
        "catalog_id": catalog_id,
        "status": "active",
        "display_name": assignment.get("display_name") or "Agente IA",
    }


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


def _stop_active_dify_for_conversation(conversation_id: str, tenant_id: str) -> bool:
    """
    Para o takeover Dify ativo de uma conversa (idempotente).

    - Atualiza ai_dify_conversation_state.status='stopped' filtrando por tenant_id
    - Em caso de sucesso (rowcount>0), emite broadcast WS para remover badge
    """
    if not conversation_id or not tenant_id:
        return False
    from django.db import transaction
    try:
        with transaction.atomic(), _conn.cursor() as cur:
            cur.execute(
                "UPDATE ai_dify_conversation_state "
                "SET status = 'stopped', updated_at = now() "
                "WHERE conversation_id = %s AND tenant_id = %s AND status = 'active'",
                [str(conversation_id), str(tenant_id)],
            )
            affected = cur.rowcount
    except Exception as exc:
        logger.error(
            "❌ [DIFY] Falha ao parar takeover (conversation=%s tenant=%s): %s",
            conversation_id,
            tenant_id,
            exc,
            exc_info=True,
        )
        return False

    if affected and affected > 0:
        try:
            from apps.chat.utils.websocket import broadcast_to_tenant

            broadcast_to_tenant(
                tenant_id=str(tenant_id),
                event_type="dify_agent_state_changed",
                data={
                    "conversation_id": str(conversation_id),
                    "status": "stopped",
                    "catalog_id": None,
                    "display_name": "",
                },
            )
        except Exception as ws_exc:
            logger.warning(
                "⚠️ [DIFY] Broadcast stop takeover falhou (não crítico) conv=%s: %s",
                conversation_id,
                ws_exc,
            )
        return True
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
        # Log dos valores enviados (truncados) para conferência
        preview = {k: (s[:60] + "…" if len(s := str(v)) > 60 else str(v)) for k, v in resolved.items()}
        logger.info("🤖 [DIFY] inputs enviados ao Dify: %s", preview)

    dify_user = _normalize_dify_user(tenant_id, (agent.dify_app_id or ''), contact_phone)
    effective_prev_conv_id = prev_dify_conv_id
    if not effective_prev_conv_id:
        # Tentar retomar memória do Dify por telefone (isolado por tenant+agente)
        resumed = _fetch_dify_conversation_for_user(base_url, api_key, dify_user, agent.id)
        if resumed:
            effective_prev_conv_id = resumed
            logger.info(
                "🤖 [DIFY] Retomando conversa anterior por user (len=%s) → dify_conv_id=%s conversa=%s",
                len(dify_user),
                resumed,
                conv_id,
            )

    payload: dict = {
        'inputs': resolved,
        'query': msg_content,
        'response_mode': 'blocking',
        'user': dify_user,
    }
    if effective_prev_conv_id:
        payload['conversation_id'] = effective_prev_conv_id

    dify_answer, new_dify_conv_id, http_status, err_body = _call_dify_api(base_url, api_key, payload, agent.id)
    if dify_answer is None:
        # Se o conversation_id antigo for inválido/expirado, tentar 1x sem conversation_id.
        if payload.get("conversation_id"):
            logger.warning(
                "⚠️ [DIFY] Falha com conversation_id; tentando novamente sem conversation_id. "
                "conversa=%s status=%s",
                conv_id,
                http_status,
            )
            retry_payload = dict(payload)
            retry_payload.pop("conversation_id", None)
            dify_answer, new_dify_conv_id, http_status, err_body = _call_dify_api(
                base_url, api_key, retry_payload, agent.id
            )
        if dify_answer is None:
            return False

    # ── Fase 4: persistir dify_conversation_id (transaction curta) ───────────────
    # Importante: persistir ANTES de qualquer early-return por instrução, para manter memória.
    if new_dify_conv_id and new_dify_conv_id != effective_prev_conv_id:
        _update_dify_conversation_id(state_id, new_dify_conv_id, tenant_id)

    # ── Fase 4.5: instruções universais (transfer/close) ─────────────────────────
    # Executa ações e remove trechos #{"..."} antes de salvar/enviar ao cliente.
    try:
        from apps.chat.services.flow_control import process_bot_control_instruction_single

        cleaned_text, ctrl_meta = process_bot_control_instruction_single(
            conversation, str(dify_answer or ""), source="dify"
        )
        dify_answer = cleaned_text
        if ctrl_meta.get("recognized"):
            logger.info(
                "🤖 [DIFY] Instrução #{} processada (closed=%s transferred=%s) conversa=%s",
                bool(ctrl_meta.get("closed")),
                bool(ctrl_meta.get("transferred")),
                conv_id,
            )
        if ctrl_meta.get("closed") or ctrl_meta.get("transferred"):
            # Regra: após transferência/encerramento, parar takeover automaticamente.
            _stop_active_dify_for_conversation(conv_id, tenant_id)
        # Se fechou ou a instrução consumiu toda a mensagem, não enviar texto ao cliente.
        if (ctrl_meta.get("closed") or ctrl_meta.get("transferred")) and not (dify_answer and dify_answer.strip()):
            logger.info(
                "🤖 [DIFY] Resposta consumida por instrução (closed=%s transferred=%s) — nada a enviar. conversa=%s",
                bool(ctrl_meta.get("closed")),
                bool(ctrl_meta.get("transferred")),
                conv_id,
            )
            return True
    except Exception as exc:
        logger.warning("⚠️ [DIFY] Falha ao processar instruções #{}: %s", exc, exc_info=True)

    if not dify_answer:
        logger.warning(
            "⚠️ [DIFY] Agente %s retornou resposta vazia para conversa %s — "
            "tentando enviar mensagem de fallback ao cliente.",
            agent.dify_app_id, conv_id
        )
        # Tentar obter mensagem de fallback configurada nas settings do tenant
        fallback_msg = _get_dify_empty_response_fallback(tenant)
        if fallback_msg:
            _save_and_send_reply(
                conversation, fallback_msg, agent.dify_app_id, conv_id, effective_instance
            )
        # Retornar True: a mensagem foi tratada pelo takeover (mesmo sem resposta útil)
        # para que o fluxo normal não processe esta mensagem em paralelo
        return True

    # ── Fase 5: salvar no banco e enfileirar envio ────────────────────────────────
    return _save_and_send_reply(
        conversation, dify_answer, agent.dify_app_id, conv_id, effective_instance
    )


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


def _call_dify_api(base_url: str, api_key: str, payload: dict, agent_id) -> tuple[str | None, str, int | None, str]:
    """
    Chama o endpoint /v1/chat-messages do Dify.
    Retorna (answer, dify_conversation_id, http_status, error_body).
    - Em sucesso: (answer, conv_id, 200/201, '')
    - Em erro HTTP: (None, '', status_code, body_preview)
    - Em exceção: (None, '', None, str(exc))
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
                return None, '', resp.status_code, (resp.text[:500] if isinstance(resp.text, str) else '')
            data = resp.json()
            answer = data.get('answer') or ''
            conv_id = data.get('conversation_id') or ''
            logger.info(
                "🤖 [DIFY] answer_len=%s dify_conv_id=%s agente=%s",
                len(answer), conv_id, agent_id
            )
            return answer, conv_id, resp.status_code, ''
    except Exception as exc:
        logger.error("❌ [DIFY] Erro na chamada Dify (%s)", exc, exc_info=True)
        return None, '', None, str(exc)


def _save_and_send_reply(
    conversation, message: str, agent_app_id: str, conv_id: str, effective_instance=None
) -> bool:
    """
    Salva a resposta do Dify no banco como Message outgoing/pending e enfileira o envio
    via send_message_to_evolution.delay (mesmo fluxo usado por flow_engine e operadores humanos).

    Isso garante que a resposta:
    - Apareça no histórico do chat imediatamente (broadcast WebSocket)
    - Seja enviada ao WhatsApp pelo worker assíncrono
    - Tenha status atualizado (pending → sent/failed) após o envio

    effective_instance: quando o agente Dify tem instância específica configurada, seu
    instance_name é inserido no metadata como 'flow_prefer_instance_name' para que o
    worker de envio use a instância correta (em vez de depender de conversation.instance_name).
    """
    from django.db import transaction
    logger.info(
        "📤 [DIFY] Salvando resposta no banco → conversa=%s agente=%s msg_len=%s",
        conv_id, agent_app_id, len(message)
    )
    try:
        from apps.chat.models import Message
        from apps.chat.tasks import send_message_to_evolution
        from apps.chat.utils.websocket import broadcast_message_received

        # Construir metadata: registra origem Dify e inclui assinatura por padrão.
        # A assinatura final é aplicada no worker usando (sender_name + include_signature).
        meta: dict = {
            'source': 'dify',
            'dify_agent_app_id': agent_app_id,
            'include_signature': True,
        }
        if effective_instance:
            inst_name = getattr(effective_instance, 'instance_name', None) or ''
            if inst_name:
                meta['flow_prefer_instance_name'] = inst_name

        # Nome para assinatura: preferir o configurado no agente; fallback para app_id.
        signature_name = ''
        try:
            from apps.ai.models import DifyAppCatalogItem
            item = DifyAppCatalogItem.objects.filter(
                tenant_id=getattr(conversation, 'tenant_id', None),
                dify_app_id=agent_app_id,
            ).only('signature_name', 'display_name').first()
            if item:
                signature_name = (getattr(item, 'signature_name', '') or '').strip() or (getattr(item, 'display_name', '') or '').strip()
        except Exception:
            signature_name = ''

        with transaction.atomic():
            msg = Message.objects.create(
                conversation=conversation,
                sender=None,  # bot — sem usuário humano
                sender_name=(signature_name or agent_app_id)[:255],
                content=message,
                direction='outgoing',
                status='pending',
                is_internal=False,
                metadata=meta,
            )
            # Lançar envio somente após commit para garantir que a mensagem está no banco
            msg_id = str(msg.id)
            transaction.on_commit(lambda: send_message_to_evolution.delay(msg_id))

        # Broadcast WebSocket fora da transaction (after commit)
        # O worker também fará um broadcast ao marcar 'sent', mas este garante
        # que a mensagem apareça no chat imediatamente com status 'pending'
        try:
            broadcast_message_received(msg)
        except Exception as ws_exc:
            logger.warning(
                "⚠️ [DIFY] Broadcast WebSocket falhou (não crítico): %s", ws_exc
            )

        logger.info(
            "✅ [DIFY] Resposta salva (message_id=%s) e enfileirada para envio → conversa=%s",
            msg_id, conv_id
        )
        return True
    except Exception as exc:
        logger.error("❌ [DIFY] Erro ao salvar/enfileirar resposta (%s)", exc, exc_info=True)
        return False
