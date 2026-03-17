"""
Integração com Typebot: execução de fluxos via API (startChat / continueChat).
Quando Flow.typebot_public_id está preenchido, o fluxo é executado pelo Typebot;
as mensagens retornadas pela API são enviadas ao WhatsApp via Message + enqueue_send_message_batch (ordem preservada).

Instruções no texto: trechos #{"chave": valor} são interpretados (closeTicket, transferTo),
executados e removidos antes de enviar ao cliente.
"""
import json
import logging
from typing import Any, List, Optional, Tuple

import requests
from django.conf import settings
from django.db import IntegrityError
from django.db import transaction

from apps.chat.models import Conversation, Message
from apps.chat.models_flow import Flow, ConversationFlowState, FlowTypebotMap
from apps.chat.redis_streams import enqueue_send_message_batch, enqueue_send_message
from apps.tenancy.services import get_or_create_typebot_workspace

logger = logging.getLogger(__name__)

# Base default da API de chat (viewer) do Typebot:
# - Se o Flow definir typebot_base_url, ela prevalece (_typebot_base_url).
# - Caso contrário, usamos TYPEBOT_VIEWER_BASE das settings (self-host) quando definido.
# - Se nenhuma das duas estiver definida, caímos em um default seguro (typebot.io),
#   apenas para não quebrar ambientes onde o Typebot ainda não foi configurado.
DEFAULT_TYPEBOT_BASE = getattr(settings, "TYPEBOT_VIEWER_BASE", None) or "https://typebot.io/api/v1"
MAX_INSTRUCTION_JSON_LENGTH = 500
CLOSE_KEYS = ("closeTicket", "encerrar", "closeConversation")
TRANSFER_KEYS = ("transferTo", "transferToDepartment")


def _find_matching_brace(text: str, open_pos: int) -> int:
    """
    Encontra o índice do '}' que fecha o '{' em open_pos, respeitando strings em double-quotes
    (e aspas escapadas \\" e barra escapada \\\\).
    Retorna -1 se não encontrar dentro de MAX_INSTRUCTION_JSON_LENGTH caracteres.
    """
    if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
        return -1
    depth = 1
    i = open_pos + 1
    limit = min(len(text), open_pos + MAX_INSTRUCTION_JSON_LENGTH)
    in_string = False
    while i < limit:
        c = text[i]
        if in_string:
            if c == "\\":
                if i + 1 >= limit:
                    break  # backslash no final da string (JSON inválido)
                i += 2  # skip escaped char
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == "{":
            depth += 1
            i += 1
            continue
        if c == "}":
            depth -= 1
            if depth == 0:
                return i
            i += 1
            continue
        i += 1
    return -1


def _typebot_base_url(flow: Flow) -> str:
    """
    Resolve a URL base da API de chat (viewer) do Typebot para um fluxo:
    - Se Flow.typebot_base_url estiver preenchido, ela é usada (normalizada com /api/v1).
    - Caso contrário, usa TYPEBOT_VIEWER_BASE das settings (self-host) quando definida.
    - Em último caso, usa DEFAULT_TYPEBOT_BASE (typebot.io) como fallback.
    """
    base = (getattr(flow, "typebot_base_url", None) or "").strip().rstrip("/")
    if base:
        # Se o campo armazenar a URL raiz (ex.: https://typebot.alrea.ai), acrescenta /api/v1
        # Se já vier com /api/v1, respeita.
        return f"{base}/api/v1" if "/api/v1" not in base else base
    return DEFAULT_TYPEBOT_BASE


def _typebot_public_id(flow: Flow) -> Optional[str]:
    pid = (getattr(flow, "typebot_public_id", None) or "").strip()
    return pid or None


def _get_typebot_admin_base() -> Optional[str]:
    """
    Base da API admin do Typebot com sufixo /api/v1, derivada de settings.TYPEBOT_API_BASE.
    Ex.: https://typebot.alrea.ai -> https://typebot.alrea.ai/api/v1
    """
    # Admin API fica no builder (dashboard)
    base = (getattr(settings, "TYPEBOT_API_BASE", None) or "").strip().rstrip("/")
    if not base:
        return None
    return base if base.endswith("/api/v1") else f"{base}/api/v1"


def _resolve_typebot_internal_id_from_public_id(flow: Flow) -> Optional[str]:
    """
    Em alguns casos (self-host), o front só conhece o publicId.
    Para embutir o editor (builder) precisamos do internal id.

    Estratégia:
    - Usa API admin para listar typebots do workspace do tenant
    - Encontra o item com publicId == flow.typebot_public_id
    """
    public_id = (getattr(flow, "typebot_public_id", None) or "").strip()
    if not public_id or not getattr(flow, "tenant_id", None):
        return None

    admin_base = _get_typebot_admin_base()
    api_key = (getattr(settings, "TYPEBOT_ADMIN_API_KEY", None) or "").strip()
    if not admin_base or not api_key:
        return None

    try:
        tenant = getattr(flow, "tenant", None)
        if not tenant:
            from apps.tenancy.models import Tenant

            tenant = Tenant.objects.filter(id=flow.tenant_id).first()
        if not tenant:
            return None
        workspace = get_or_create_typebot_workspace(tenant)
    except Exception:
        return None

    if not workspace:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Builder API: POST /api/v1/typebots com workspaceId
    url = f"{admin_base}/typebots"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("typebots") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return None
        for it in items:
            if not isinstance(it, dict):
                continue
            pid = (it.get("publicId") or it.get("public_id") or "").strip()
            if pid != public_id:
                continue
            internal = (it.get("id") or it.get("_id") or "").strip()
            return internal or None
    except Exception:
        return None
    return None


def ensure_typebot_bot_for_flow(flow: Flow) -> Flow:
    """
    Garante que o Flow tenha um bot Typebot associado:
    - Se já existir typebot_public_id, não faz nada.
    - Senão, tenta criar workspace (get_or_create_typebot_workspace) e depois
      criar um bot via API admin do Typebot, salvando publicId/internalId.
    Em qualquer erro, apenas loga e retorna o Flow sem quebrar o request.
    """
    if not flow or not getattr(flow, "tenant_id", None):
        return flow

    # Idempotência (evita criar 2-4x quando create/retrieve disparam juntos)
    try:
        with transaction.atomic():
            locked_flow = Flow.objects.select_for_update().filter(id=flow.id).first()
            if locked_flow:
                flow = locked_flow

            existing_map = FlowTypebotMap.objects.select_for_update().filter(flow_id=flow.id, tenant_id=flow.tenant_id).first()
            if existing_map and (existing_map.typebot_internal_id or "").strip():
                # Sincronizar campos legados no Flow (para UI/compatibilidade)
                try:
                    flow.typebot_internal_id = (existing_map.typebot_internal_id or "").strip()
                    flow.typebot_public_id = (existing_map.typebot_public_id or "").strip()
                    if (existing_map.typebot_public_id or "").strip() and not (flow.typebot_base_url or "").strip():
                        base = (getattr(settings, "TYPEBOT_VIEWER_BASE", None) or "").strip().rstrip("/")
                        flow.typebot_base_url = base
                    flow.save(update_fields=["typebot_internal_id", "typebot_public_id", "typebot_base_url"])
                except Exception:
                    pass
                return flow

            # Se ainda não existe map, mas já existe internal_id no Flow, cria o vínculo usando o workspace do tenant.
            if not existing_map and (getattr(flow, "typebot_internal_id", None) or "").strip():
                try:
                    tenant = getattr(flow, "tenant", None)
                    if not tenant:
                        from apps.tenancy.models import Tenant

                        tenant = Tenant.objects.filter(id=flow.tenant_id).first()
                    if tenant:
                        ws = get_or_create_typebot_workspace(tenant)
                        if ws:
                            FlowTypebotMap.objects.create(
                                tenant_id=flow.tenant_id,
                                flow_id=flow.id,
                                typebot_workspace_id=ws.workspace_id,
                                typebot_internal_id=(flow.typebot_internal_id or "").strip(),
                                typebot_public_id=(flow.typebot_public_id or "").strip(),
                                bot_name=(flow.name or "").strip()[:255],
                            )
                except Exception:
                    pass
    except Exception:
        # Não quebrar request por falha no lock
        pass

    admin_base = _get_typebot_admin_base()
    api_key = (getattr(settings, "TYPEBOT_ADMIN_API_KEY", None) or "").strip()
    if not admin_base or not api_key:
        logger.info(
            "[TYPEBOT][BOT] Admin base ou API key não configuradas; "
            "não será criado bot automático para flow=%s tenant=%s",
            getattr(flow, "id", None),
            getattr(flow, "tenant_id", None),
        )
        return flow

    try:
        tenant = getattr(flow, "tenant", None)
        if not tenant:
            from apps.tenancy.models import Tenant

            tenant = Tenant.objects.filter(id=flow.tenant_id).first()
        if not tenant:
            return flow
        workspace = get_or_create_typebot_workspace(tenant)
    except Exception as e:
        logger.warning(
            "[TYPEBOT][BOT] Erro ao garantir workspace para flow=%s tenant=%s: %s",
            getattr(flow, "id", None),
            getattr(flow, "tenant_id", None),
            e,
            exc_info=True,
        )
        return flow

    if not workspace:
        return flow

    # Builder API: POST /api/v1/typebots (workspaceId no payload)
    url = f"{admin_base}/typebots"
    display_name = (flow.name or "Fluxo Sense").strip()
    try:
        from apps.authn.models import Department

        dept_name = None
        if getattr(flow, "department_id", None):
            dept = Department.objects.filter(id=flow.department_id).first()
            if dept:
                dept_name = dept.name
        if dept_name:
            display_name = f"{display_name} - {dept_name}"
    except Exception:
        # Qualquer erro aqui é apenas cosmético no nome
        pass

    payload: dict[str, Any] = {
        "workspaceId": workspace.workspace_id,
        "typebot": {
            "name": display_name[:80] or "Fluxo Sense",
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
        # Algumas versões retornam o objeto diretamente; outras retornam dentro de "typebot"
        tb = data.get("typebot") if isinstance(data, dict) else None
        tb = tb if isinstance(tb, dict) else data if isinstance(data, dict) else {}
        public_id = (tb.get("publicId") or tb.get("public_id") or tb.get("publicID") or "").strip()
        internal_id = (tb.get("id") or tb.get("_id") or tb.get("typebotId") or "").strip()
        if not internal_id:
            logger.warning(
                "[TYPEBOT][BOT] Resposta sem id ao criar bot flow=%s workspace=%s data_keys=%s typebot_keys=%s",
                getattr(flow, "id", None),
                workspace.workspace_id,
                list(data.keys()) if isinstance(data, dict) else [],
                list(tb.keys()) if isinstance(tb, dict) else [],
            )
            return flow
    except requests.RequestException as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        body_text = None
        try:
            body_text = getattr(getattr(e, "response", None), "text", None)
        except Exception:
            body_text = None
        logger.warning(
            "[TYPEBOT][BOT] Falha ao criar bot para flow=%s workspace=%s http=%s body=%s err=%s",
            getattr(flow, "id", None),
            workspace.workspace_id,
            status_code,
            (body_text[:500] if isinstance(body_text, str) else None),
            e,
        )
        return flow
    except Exception as e:
        logger.warning(
            "[TYPEBOT][BOT] Erro inesperado ao criar bot para flow=%s workspace=%s: %s",
            getattr(flow, "id", None),
            workspace.workspace_id,
            e,
            exc_info=True,
        )
        return flow

    # Persistir IDs no vínculo (tabela 1:1) e também no Flow (compatibilidade/UI)
    try:
        with transaction.atomic():
            locked_flow = Flow.objects.select_for_update().filter(id=flow.id).first()
            if locked_flow:
                flow = locked_flow

            # Base do viewer (chat)
            viewer_base = (getattr(settings, "TYPEBOT_VIEWER_BASE", None) or "").strip()
            if viewer_base.endswith("/api/v1"):
                viewer_base = viewer_base[: -len("/api/v1")]
            viewer_base = viewer_base.rstrip("/")

            # Cria/atualiza map (1:1)
            try:
                m, created = FlowTypebotMap.objects.select_for_update().get_or_create(
                    tenant_id=flow.tenant_id,
                    flow_id=flow.id,
                    defaults={
                        "typebot_workspace_id": workspace.workspace_id,
                        "typebot_internal_id": internal_id,
                        "typebot_public_id": public_id or "",
                        "bot_name": (display_name or flow.name or "").strip()[:255],
                        "status": FlowTypebotMap.STATUS_ACTIVE,
                    },
                )
                if not created:
                    m.typebot_workspace_id = workspace.workspace_id
                    m.typebot_internal_id = internal_id
                    if public_id:
                        m.typebot_public_id = public_id
                    m.bot_name = (display_name or flow.name or "").strip()[:255]
                    m.status = FlowTypebotMap.STATUS_ACTIVE
                    m.save(update_fields=["typebot_workspace_id", "typebot_internal_id", "typebot_public_id", "bot_name", "status", "updated_at"])
            except IntegrityError:
                # Outro request criou ao mesmo tempo; recarregar
                m = FlowTypebotMap.objects.filter(tenant_id=flow.tenant_id, flow_id=flow.id).first()

            # Preenche também no Flow (campos existentes)
            flow.typebot_internal_id = internal_id
            if public_id:
                flow.typebot_public_id = public_id
            if viewer_base:
                flow.typebot_base_url = viewer_base
            flow.save(update_fields=["typebot_internal_id", "typebot_public_id", "typebot_base_url"])
        logger.info(
            "[TYPEBOT][BOT] Bot criado e associado ao flow=%s tenant=%s workspace=%s publicId=%s",
            flow.id,
            flow.tenant_id,
            workspace.workspace_id,
            public_id or "-",
        )
    except Exception as e:
        logger.warning(
            "[TYPEBOT][BOT] Erro ao salvar IDs do bot para flow=%s: %s",
            getattr(flow, "id", None),
            e,
            exc_info=True,
        )
    return flow


def _extract_text_from_messages(data: dict) -> List[str]:
    """Extrai textos da lista 'messages' da resposta do Typebot (startChat ou continueChat)."""
    messages = data.get("messages") if isinstance(data.get("messages"), list) else []
    texts = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("type") == "text":
            content = m.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content.strip())
                continue
            if not isinstance(content, dict):
                if content:
                    texts.append(str(content).strip())
                continue
            # content pode ser { type: "markdown", markdown: "..." } (quando textBubbleContentFormat=markdown)
            if content.get("type") == "markdown":
                md = content.get("markdown")
                if isinstance(md, str) and md.strip():
                    texts.append(md.strip())
                    continue
            # content pode ser { type: "richText", richText: [...] } (estrutura TipTap/block)
            rt = content.get("richText")
            if rt is not None:
                part = _rich_text_to_plain(rt)
                if part:
                    texts.append(part)
                    continue
            if content:
                texts.append(str(content).strip())
    return texts


def _rich_text_to_plain(rt: Any) -> str:
    """Converte richText (array ou objeto aninhado) em texto plano; extrai qualquer campo 'text' encontrado."""
    parts: List[str] = []

    def collect(obj: Any) -> None:
        if isinstance(obj, str) and obj.strip():
            parts.append(obj.strip())
        elif isinstance(obj, list):
            for item in obj:
                collect(item)
        elif isinstance(obj, dict):
            if obj.get("text") is not None:
                parts.append(str(obj["text"]).strip())
            for key in ("content", "richText", "children"):
                if key in obj and obj[key]:
                    collect(obj[key])

    collect(rt)
    return "\n".join(p for p in parts if p)


def _send_texts_to_whatsapp(conversation: Conversation, texts: List[str], metadata: Optional[dict] = None) -> None:
    """
    Cria uma Message por texto e enfileira envio para Evolution/Meta.
    Usa um único batch (message_ids em ordem) para preservar a ordem das mensagens do Typebot no WhatsApp.
    """
    if not conversation or not texts:
        return
    meta = dict(metadata or {})
    meta["flow_engine"] = "typebot"
    try:
        with transaction.atomic():
            message_ids: List[str] = []
            for content in texts:
                if not (content and str(content).strip()):
                    continue
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=content,
                    direction="outgoing",
                    status="pending",
                    is_internal=False,
                    metadata=meta,
                )
                message_ids.append(str(message.id))
            if message_ids:
                def _enqueue_after_commit(ids: List[str]) -> None:
                    try:
                        enqueue_send_message_batch(ids)
                    except Exception as e:
                        logger.warning(
                            "[TYPEBOT] Batch enqueue falhou (%s), enfileirando mensagens uma a uma (ordem pode variar): %s",
                            e,
                            ids[:3],
                        )
                        for mid in ids:
                            try:
                                enqueue_send_message(str(mid))
                            except Exception as e2:
                                logger.exception("[TYPEBOT] Erro ao enfileirar mensagem %s: %s", mid, e2)
                transaction.on_commit(lambda: _enqueue_after_commit(message_ids))
        logger.info("[TYPEBOT] Batch enfileirado conversation=%s messages=%s", conversation.id, len(message_ids))
    except Exception as e:
        logger.exception("[TYPEBOT] Erro ao criar/enfileirar mensagens: %s", e)


def close_conversation_from_typebot(conversation: Conversation) -> bool:
    """
    Fecha a conversa (mensagens não lidas -> lidas, status=closed, department/assigned_to=None,
    remove ConversationFlowState). Usado pelo webhook Typebot e por instruções no texto.
    Retorna True se fechou com sucesso.
    """
    if not conversation or getattr(conversation, "status", None) == "closed":
        return True
    try:
        with transaction.atomic():
            Message.objects.filter(
                conversation=conversation,
                direction="incoming",
                status__in=["sent", "delivered"],
            ).update(status="seen")
            conversation.status = "closed"
            conversation.department = None
            conversation.assigned_to = None
            conversation.save(update_fields=["status", "department", "assigned_to"])
            ConversationFlowState.objects.filter(conversation_id=conversation.id).delete()
        conversation.refresh_from_db()
        logger.info("[TYPEBOT] Conversa %s fechada (instrução ou webhook)", conversation.id)
        return True
    except Exception as e:
        logger.warning("[TYPEBOT] Erro ao fechar conversa: %s", e, exc_info=True)
        return False


def _execute_transfer_by_department_name(conversation: Conversation, department_name: str) -> bool:
    """Transfere conversa para o departamento identificado pelo nome (tenant + name__iexact)."""
    if not conversation or not conversation.tenant_id:
        return False
    name = (department_name if isinstance(department_name, str) else str(department_name)).strip()
    if not name:
        return False
    from apps.authn.models import Department

    dept = Department.objects.filter(
        tenant_id=conversation.tenant_id,
        name__iexact=name,
    ).first()
    if not dept:
        logger.warning("[TYPEBOT] Departamento não encontrado por nome: %r conversation=%s", name, conversation.id)
        return False
    try:
        old_department = conversation.department
        with transaction.atomic():
            conversation.department = dept
            conversation.assigned_to = None
            conversation.status = "open"
            conversation.save(update_fields=["department", "assigned_to", "status"])
            ConversationFlowState.objects.filter(conversation_id=conversation.id).delete()
        old_name = old_department.name if old_department else "Inbox"
        transfer_msg = (
            f"Conversa transferida:\nDe: {old_name} (Não atribuído)\nPara: {dept.name} (Não atribuído)\n(por Typebot)"
        )
        Message.objects.create(
            conversation=conversation,
            sender=None,
            content=transfer_msg,
            direction="outgoing",
            status="sent",
            is_internal=True,
        )
        from apps.chat.services.flow_engine import try_send_flow_start

        try_send_flow_start(conversation)
        from apps.chat.utils.websocket import broadcast_conversation_updated

        broadcast_conversation_updated(conversation)
        transfer_message_text = (getattr(dept, "transfer_message", None) or "").strip()
        if not transfer_message_text:
            transfer_message_text = (
                f"Sua conversa foi transferida para o departamento {dept.name}. Em breve você será atendido."
            )
        from django.db.models import Q
        from apps.notifications.models import WhatsAppInstance
        from apps.notifications.whatsapp_providers import get_sender

        wa_instance = None
        inst_name = (conversation.instance_name or "").strip()
        if inst_name:
            wa_instance = WhatsAppInstance.objects.filter(
                Q(instance_name=inst_name) | Q(evolution_instance_name=inst_name),
                tenant_id=conversation.tenant_id,
                is_active=True,
                status="active",
            ).first()
            if not wa_instance and inst_name.isdigit():
                wa_instance = WhatsAppInstance.objects.filter(
                    phone_number_id=inst_name,
                    integration_type=WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD,
                    tenant_id=conversation.tenant_id,
                    is_active=True,
                    status="active",
                ).first()
        if not wa_instance:
            wa_instance = WhatsAppInstance.objects.filter(
                tenant_id=conversation.tenant_id,
                is_active=True,
                status="active",
            ).first()
        if wa_instance:
            sender = get_sender(wa_instance)
            if sender:
                to_phone = (conversation.contact_phone or "").replace("@g.us", "").replace("@s.whatsapp.net", "").strip()
                if to_phone:
                    try:
                        sender.send_text(to_phone, transfer_message_text)
                    except Exception as send_err:
                        logger.warning("[TYPEBOT] Transferência OK; falha ao enviar mensagem ao cliente: %s", send_err)
        conversation.refresh_from_db()
        logger.info("[TYPEBOT] Transferência por instrução: conversation=%s -> %s", conversation.id, dept.name)
        return True
    except Exception as e:
        logger.warning("[TYPEBOT] Erro ao transferir por nome: %s", e, exc_info=True)
        return False


def _process_instructions_in_texts(conversation: Conversation, texts: List[str]) -> List[str]:
    """
    Detecta trechos #{"chave": valor} em cada texto, executa closeTicket/transferTo e remove o trecho.
    Retorna lista de textos limpos. Em falha, retorna a lista original.
    Após executar "encerrar", não executa mais instruções no mesmo lote.
    """
    if not conversation:
        return []
    if not isinstance(texts, list):
        return []
    if not conversation.tenant_id:
        return list(texts)
    cleaned: List[str] = []
    closed = False
    for raw in texts:
        if not isinstance(raw, str):
            if raw is not None and str(raw).strip():
                cleaned.append(str(raw).strip())
            continue
        text = raw.strip()
        if not text:
            continue
        pos = 0
        while pos < len(text):
            idx = text.find("#{", pos)
            if idx < 0:
                break
            end = _find_matching_brace(text, idx + 1)
            if end < 0:
                pos = idx + 2
                continue
            # Incluir "{" e "}" para obter JSON válido (ex.: #{"closeTicket": true} -> segment = {"closeTicket": true})
            segment = text[idx + 1 : end + 1].strip()[:MAX_INSTRUCTION_JSON_LENGTH]
            pos = end + 1
            try:
                obj = json.loads(segment)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(obj, dict):
                continue
            recognized = False
            if not closed:
                for key in CLOSE_KEYS:
                    if key in obj and obj[key]:
                        recognized = True
                        close_conversation_from_typebot(conversation)
                        closed = True
                        break
            if not closed:
                for key in TRANSFER_KEYS:
                    if key in obj:
                        val = obj[key]
                        name = (val if isinstance(val, str) else str(val)).strip() if val is not None else ""
                        if name:
                            recognized = True
                            _execute_transfer_by_department_name(conversation, name)
                        break
            if recognized:
                before = text[:idx].rstrip()
                after = text[pos:].lstrip()
                text = f"{before}\n{after}".strip() if before and after else (before or after)
                pos = 0
        if text and text.strip():
            cleaned.append(text.strip())
    return cleaned


def start_typebot_flow(conversation: Conversation, flow: Flow) -> Tuple[bool, int]:
    """
    Inicia fluxo Typebot: chama startChat, persiste session_id no ConversationFlowState,
    envia as mensagens retornadas ao WhatsApp.
    Retorna (True, mensagens_enfileiradas) se iniciou com sucesso; (False, 0) em caso de falha.
    """
    public_id = _typebot_public_id(flow)
    if not public_id:
        return (False, 0)
    base = _typebot_base_url(flow)
    url = f"{base}/typebots/{public_id}/startChat"
    prefilled = {
        "conversation_id": str(conversation.id),
        "contact_phone": (conversation.contact_phone or "").strip(),
        "contact_name": (conversation.contact_name or "").strip() or "Contato",
        "tenant_id": str(conversation.tenant_id),
    }
    if conversation.department_id:
        prefilled["department_id"] = str(conversation.department_id)
    # Alinhar com cadastro de contato: enviar NomeContato, NumeroFone, email se o contato estiver cadastrado
    try:
        from django.db.models import Q
        from apps.contacts.models import Contact
        from apps.contacts.signals import normalize_phone_for_search
        phone_norm = normalize_phone_for_search(conversation.contact_phone or "")
        if phone_norm and conversation.tenant_id:
            contact = Contact.objects.filter(
                Q(tenant_id=conversation.tenant_id) & (Q(phone=phone_norm) | Q(phone=conversation.contact_phone))
            ).first()
            if contact:
                if "NomeContato" not in prefilled:
                    prefilled["NomeContato"] = (contact.name or conversation.contact_name or "").strip() or "Contato"
                if "NumeroFone" not in prefilled:
                    prefilled["NumeroFone"] = (contact.phone or conversation.contact_phone or "").strip()
                if "number" not in prefilled:
                    prefilled["number"] = (contact.phone or conversation.contact_phone or "").strip()
                if "pushName" not in prefilled:
                    prefilled["pushName"] = (contact.name or conversation.contact_name or "").strip() or ""
                if contact.email and "email" not in prefilled:
                    prefilled["email"] = (contact.email or "").strip()
    except Exception as e:
        logger.debug("[TYPEBOT] Contato não encontrado ou erro ao buscar: %s", e)
    # Garantir nomes padrão se ainda não definidos (evitar variável vazia no Typebot, ex.: ", vou precisar...")
    if "NomeContato" not in prefilled:
        prefilled["NomeContato"] = prefilled.get("contact_name") or "Contato"
    if "NumeroFone" not in prefilled:
        prefilled["NumeroFone"] = prefilled.get("contact_phone") or ""
    if "pushName" not in prefilled or not (prefilled.get("pushName") or "").strip():
        prefilled["pushName"] = prefilled.get("contact_name") or "Contato"
    extra = getattr(flow, "typebot_prefilled_extra", None)
    if isinstance(extra, dict) and extra:
        for k, v in extra.items():
            if k and isinstance(v, (str, int, float, bool)):
                prefilled[str(k).strip()] = str(v)
            elif k and v is not None:
                prefilled[str(k).strip()] = str(v)
    payload = {
        "prefilledVariables": prefilled,
        "textBubbleContentFormat": "markdown",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("[TYPEBOT] startChat falhou: %s", e)
        return (False, 0)
    session_id = (data.get("sessionId") or "").strip()
    if not session_id:
        logger.warning("[TYPEBOT] startChat não retornou sessionId")
        return (False, 0)
    try:
        with transaction.atomic():
            state = ConversationFlowState.objects.filter(conversation_id=conversation.id).first()
            if not state:
                state, _ = ConversationFlowState.objects.update_or_create(
                    conversation_id=conversation.id,
                    defaults={
                        "flow_id": flow.id,
                        "current_node_id": None,
                        "typebot_session_id": session_id,
                    },
                )
            else:
                state.flow_id = flow.id
                state.current_node_id = None
                state.typebot_session_id = session_id
                state.save(update_fields=["flow_id", "current_node_id", "typebot_session_id"])
            result_id = (data.get("resultId") or "").strip()
            if result_id:
                if state.metadata is None:
                    state.metadata = {}
                state.metadata["typebot_result_id"] = result_id
                state.save(update_fields=["metadata"])
        texts = _extract_text_from_messages(data)
        if not texts:
            raw_messages = data.get("messages") if isinstance(data.get("messages"), list) else []
            msg_types = [m.get("type") for m in raw_messages if isinstance(m, dict)]
            logger.warning(
                "[TYPEBOT] startChat retornou 0 mensagens de texto conversation=%s sessionId=%s raw_messages=%s types=%s. "
                "Garanta que o primeiro bloco do Typebot envia uma mensagem de texto (tipo text).",
                conversation.id, session_id[:16], len(raw_messages), msg_types,
            )
        try:
            texts = _process_instructions_in_texts(conversation, texts)
        except Exception as e:
            logger.warning("[TYPEBOT] Erro ao processar instruções no texto, usando textos originais: %s", e)
        _send_texts_to_whatsapp(conversation, texts)
        logger.info("[TYPEBOT] Fluxo iniciado conversation=%s sessionId=%s messages=%s", conversation.id, session_id[:16], len(texts))
        return (True, len(texts))
    except Exception as e:
        logger.exception("[TYPEBOT] Erro ao salvar estado ou enviar mensagens: %s", e)
        return (False, 0)


def continue_typebot_flow(conversation: Conversation, user_message: str) -> bool:
    """
    Envia a mensagem do usuário ao Typebot (continueChat) e envia as mensagens
    de resposta ao WhatsApp. Retorna True se a conversa estava em sessão Typebot e foi processada.
    """
    state = (
        ConversationFlowState.objects.filter(conversation_id=conversation.id)
        .select_related("flow")
        .first()
    )
    if not state or not (state.typebot_session_id and state.flow_id):
        return False
    flow = getattr(state, "flow", None)
    if not flow or not _typebot_public_id(flow):
        return False
    base = _typebot_base_url(flow)
    url = f"{base}/sessions/{state.typebot_session_id}/continueChat"
    # API Typebot: mensagem de texto exige propriedade "text", não "content"
    payload = {
        "message": {"type": "text", "text": user_message},
        "textBubbleContentFormat": "markdown",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code in (404, 410):
            logger.warning("[TYPEBOT] Sessão não encontrada ou expirada (HTTP %s), limpando estado", r.status_code)
            state.typebot_session_id = ""
            state.save(update_fields=["typebot_session_id"])
            return False
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("[TYPEBOT] continueChat falhou: %s", e)
        return False
    texts = _extract_text_from_messages(data) if isinstance(data, dict) else []
    try:
        texts = _process_instructions_in_texts(conversation, texts)
    except Exception as e:
        logger.warning("[TYPEBOT] Erro ao processar instruções no texto, usando textos originais: %s", e)
    _send_texts_to_whatsapp(conversation, texts)
    # Se o Typebot retornar um "input" (próximo bloco de pergunta), a sessão continua.
    # Se não houver input, opcionalmente podemos limpar a sessão ou mantê-la para histórico.
    logger.info("[TYPEBOT] continueChat processado conversation=%s messages=%s", conversation.id, len(texts))
    return True
