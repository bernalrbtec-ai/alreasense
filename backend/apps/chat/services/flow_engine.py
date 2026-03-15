"""
Motor de fluxo conversacional: processa respostas a lista/botões e envia próximas etapas.
Fluxo por Inbox ou departamento; coexistência com Welcome Menu.
"""
import logging
import re
import threading
import time
from typing import Optional, Dict, Any

from django.db import transaction

from apps.chat.models import Conversation, Message
from apps.chat.models_flow import Flow, FlowNode, FlowEdge, ConversationFlowState
from apps.authn.models import Department

logger = logging.getLogger(__name__)


def get_active_flow_for_conversation(conversation: Conversation) -> Optional[Flow]:
    """
    Retorna o fluxo ativo para o escopo da conversa (Inbox ou departamento).
    - Inbox: conversation.department_id is None, scope=inbox, department=null.
    - Departamento: conversation.department_id preenchido, scope=department, department_id igual.
    """
    flows = get_active_flows_for_conversation(conversation)
    return flows.first() if flows is not None else None


def get_active_flows_for_conversation(conversation: Conversation):
    """
    Retorna o queryset de fluxos ativos para o escopo da conversa (Inbox ou departamento).
    Usado para listar fluxos no modal "Iniciar fluxo" e para escolher qual iniciar.
    """
    if not conversation or not conversation.tenant_id:
        return Flow.objects.none()
    if conversation.department_id is None:
        return Flow.objects.filter(
            tenant_id=conversation.tenant_id,
            scope=Flow.SCOPE_INBOX,
            is_active=True,
            department__isnull=True,
        ).order_by("name")
    return Flow.objects.filter(
        tenant_id=conversation.tenant_id,
        scope=Flow.SCOPE_DEPARTMENT,
        department_id=conversation.department_id,
        is_active=True,
    ).order_by("name")


def get_start_node(flow: Flow) -> Optional[FlowNode]:
    """Retorna o nó inicial do fluxo (is_start=True ou menor order)."""
    start = flow.nodes.filter(is_start=True).first()
    if start:
        return start
    return flow.nodes.order_by("order", "name").first()


def _normalize_option_id(raw: str) -> str:
    """
    Normaliza option_id para matching (mesma regra da Evolution: só a-zA-Z0-9_-).
    Garante que list_reply.id vindo da API coincida com option_id das arestas.
    """
    if not raw or not isinstance(raw, str):
        return ""
    return (re.sub(r"[^a-zA-Z0-9_-]", "", raw.strip()))[:100]


def _build_interactive_list_payload(node: FlowNode) -> Dict[str, Any]:
    """Monta payload interactive_list a partir do nó (tipo list). Limites: 10 seções, 10 linhas por seção.
    Normaliza cada row para ter 'id' e 'title' (Meta/Evolution esperam esse formato).
    """
    sections = list(node.sections or [])[:10]
    out_sections = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        rows_raw = (sec.get("rows") or []) if isinstance(sec.get("rows"), list) else []
        rows = []
        for i, r in enumerate(rows_raw[:10]):
            if not isinstance(r, dict):
                continue
            # Meta/Evolution: id e title obrigatórios; aceitar option_id como id
            row_id = (r.get("id") or r.get("option_id") or "").strip() or f"row{i}"
            row_title = (r.get("title") or "").strip()
            if not row_title:
                continue
            rows.append({
                "id": row_id[:256],
                "title": row_title[:24],
                **({"description": (r.get("description") or "").strip()[:72]} if (r.get("description") or "").strip() else {}),
            })
        if not rows:
            continue
        out_sections.append({"title": (sec.get("title") or "").strip()[:24] or "Opções", "rows": rows})
    return {
        "body_text": (node.body_text or "").strip()[:1024],
        "button_text": (node.button_text or "").strip()[:20],
        "header_text": (node.header_text or "").strip()[:60],
        "footer_text": (node.footer_text or "").strip()[:60],
        "sections": out_sections,
    }


def _build_interactive_buttons_payload(node: FlowNode) -> Dict[str, Any]:
    """Monta payload interactive_reply_buttons a partir do nó (tipo buttons). Meta: id e title obrigatórios."""
    buttons = list(node.buttons or [])[:3]
    out = []
    for i, b in enumerate(buttons):
        if not isinstance(b, dict):
            continue
        bid = (b.get("id") or b.get("option_id") or "").strip() or f"btn{i}"
        title = (b.get("title") or "").strip()
        if not title:
            continue
        out.append({"id": bid[:100], "title": title[:20]})
    return {"body_text": (node.body_text or "").strip()[:1024], "buttons": out}


def _conversation_uses_evolution(conversation: Conversation) -> bool:
    """True se a conversa usa instância Evolution (lista/botões desativados na Evolution 2.3.7)."""
    from django.db.models import Q
    from apps.notifications.models import WhatsAppInstance
    if not conversation or not getattr(conversation, "instance_name", None):
        return False
    instance_name = (conversation.instance_name or "").strip()
    if not instance_name:
        return False
    inst = WhatsAppInstance.objects.filter(tenant_id=conversation.tenant_id).filter(
        Q(instance_name=instance_name) | Q(evolution_instance_name=instance_name),
    ).first()
    return inst is not None and getattr(inst, "integration_type", None) == WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION


def _flow_should_send_interactive(flow: Optional[Flow], conversation: Conversation) -> bool:
    """
    True se a mensagem do fluxo deve levar interactive_list/interactive_reply_buttons no metadata.
    O envio usa flow_prefer_instance_name (instância do fluxo) ou conversation.instance_name.
    Só NÃO colocamos interativo quando temos certeza de que a instância usada será Evolution.
    """
    from apps.notifications.models import WhatsAppInstance
    if not flow:
        return not _conversation_uses_evolution(conversation)
    # Fluxo tem instância preferida: envio usará ela (flow_prefer_instance_name no task)
    try:
        wa = getattr(flow, "whatsapp_instance", None)
        if wa is not None:
            return getattr(wa, "integration_type", None) == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD
    except Exception:
        pass
    # Sem instância no fluxo: usa a da conversa
    return not _conversation_uses_evolution(conversation)


def send_flow_node(conversation: Conversation, node: FlowNode) -> Optional[Message]:
    """
    Cria mensagem (texto, imagem, arquivo, lista ou botões) do nó e enfileira envio.
    Retorna a mensagem criada ou None.

    Compatível com Evolution API e Meta Cloud API:
    - message: texto puro (ambos).
    - image/file: envio via send_media do provider (Evolution ou Meta); Meta exige
      media_url acessível publicamente (GET pela Meta); Evolution aceita URL interna.
    - list/buttons: interactive_list / interactive_reply_buttons (ambos).
    """
    from apps.chat.tasks import send_message_to_evolution

    if not conversation or not node:
        logger.warning("[FLOW] conversation ou node ausente")
        return None
    try:
        flow_tenant_id = node.flow.tenant_id
    except Exception:
        logger.warning("[FLOW] Nó sem fluxo acessível (flow_id=%s)", getattr(node, "flow_id", None))
        return None
    if not conversation.tenant_id or conversation.tenant_id != flow_tenant_id:
        logger.warning("[FLOW] Tenant da conversa não coincide com o do fluxo: conversation=%s node.flow=%s", conversation.id, node.flow_id)
        return None

    content = ""
    metadata = {"flow_node_id": str(node.id), "flow_id": str(node.flow_id)}
    flow = None
    try:
        flow = getattr(node, "flow", None) or Flow.objects.select_related("whatsapp_instance").filter(pk=node.flow_id).first()
        if flow and getattr(flow, "whatsapp_instance_id", None) and getattr(flow, "whatsapp_instance", None):
            metadata["flow_prefer_instance_name"] = (flow.whatsapp_instance.instance_name or "").strip()
    except Exception:
        pass

    if node.node_type == FlowNode.NODE_TYPE_MESSAGE:
        content = (node.body_text or "").strip()
        if not content:
            logger.warning("[FLOW] Nó mensagem sem texto: %s", node.id)
            return None
    elif node.node_type == FlowNode.NODE_TYPE_IMAGE:
        media_url = (node.media_url or "").strip()[:1024]
        if not media_url:
            logger.warning("[FLOW] Nó imagem sem media_url: %s", node.id)
            return None
        content = (node.body_text or "").strip()[:1024]
        metadata["flow_media_url"] = media_url
        metadata["flow_media_type"] = "image"
    elif node.node_type == FlowNode.NODE_TYPE_FILE:
        media_url = (node.media_url or "").strip()[:1024]
        if not media_url:
            logger.warning("[FLOW] Nó arquivo sem media_url: %s", node.id)
            return None
        content = (node.body_text or "").strip()[:1024]
        metadata["flow_media_url"] = media_url
        metadata["flow_media_type"] = "document"
    elif node.node_type == FlowNode.NODE_TYPE_LIST:
        payload = _build_interactive_list_payload(node)
        if not payload.get("body_text") or not payload.get("button_text") or not payload.get("sections"):
            logger.warning("[FLOW] Nó lista inválido (body/button/sections): %s", node.id)
            return None
        content = payload["body_text"]
        if _flow_should_send_interactive(flow, conversation):
            metadata["interactive_list"] = payload
        else:
            logger.info("[FLOW] Instância Evolution: enviando nó lista como texto (listas desativadas na Evolution 2.3.7)")
    elif node.node_type == FlowNode.NODE_TYPE_BUTTONS:
        payload = _build_interactive_buttons_payload(node)
        if not payload.get("body_text") or not payload.get("buttons"):
            logger.warning("[FLOW] Nó botões inválido (body/buttons): %s", node.id)
            return None
        content = payload["body_text"]
        if _flow_should_send_interactive(flow, conversation):
            metadata["interactive_reply_buttons"] = payload
        else:
            logger.info("[FLOW] Instância Evolution: enviando nó botões como texto (botões desativados na Evolution 2.3.7)")
    else:
        logger.warning("[FLOW] Tipo de nó desconhecido: %s", node.node_type)
        return None

    try:
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender=None,
                content=content,
                direction="outgoing",
                status="pending",
                is_internal=False,
                metadata=metadata,
            )
            transaction.on_commit(lambda: send_message_to_evolution.delay(str(message.id)))
        logger.info("[FLOW] Mensagem de nó enfileirada conversation=%s node=%s", conversation.id, node.name)
        return message
    except Exception as e:
        logger.exception("[FLOW] Erro ao criar/enfileirar mensagem do nó: %s", e)
        return None


def _get_single_next_edge(node: FlowNode):
    """Se o nó tiver exatamente uma aresta 'próxima etapa' com to_node, retorna essa aresta; senão None."""
    if not node or not node.pk:
        return None
    edges = list(
        FlowEdge.objects.filter(
            from_node_id=node.pk,
            target_action=FlowEdge.TARGET_ACTION_NEXT,
        ).exclude(to_node_id__isnull=True).select_related("to_node")[:2]
    )
    return edges[0] if len(edges) == 1 else None


def _run_delay_advance(conversation_id: str, delay_node_id: str, delay_seconds: int) -> None:
    """
    Executado após delay_seconds (em thread): avança do nó timer para o próximo e envia.
    Usa conversation_id para recarregar do DB (thread pode rodar depois do request).
    """
    time.sleep(max(1, min(delay_seconds, 86400)))  # entre 1s e 24h
    try:
        conversation = Conversation.objects.filter(pk=conversation_id).first()
        if not conversation:
            return
        state = (
            ConversationFlowState.objects.filter(conversation_id=conversation_id)
            .select_related("flow", "current_node")
            .first()
        )
        if not state or str(state.current_node_id) != str(delay_node_id):
            return
        current = state.current_node
        if not current or current.node_type != FlowNode.NODE_TYPE_DELAY:
            return
        edge = _get_single_next_edge(current)
        if not edge or not edge.to_node_id:
            return
        next_node = edge.to_node
        state.current_node_id = edge.to_node_id
        state.save(update_fields=["current_node_id"])
        sent = send_flow_node(conversation, next_node)
        if sent:
            logger.info("[FLOW] Timer concluído, avançou para nó %s conversation=%s", next_node.name, conversation_id)
            _auto_advance_message_chain(conversation, state)
    except Exception as e:
        logger.exception("[FLOW] Erro ao avançar após timer: %s", e)


def _auto_advance_message_chain(conversation: Conversation, state: ConversationFlowState, max_steps: int = 20) -> None:
    """
    Se o nó atual for mensagem e tiver exatamente uma aresta para próxima etapa, avança e envia
    esse nó (sem exigir resposta do usuário). Se o próximo for nó timer, agenda espera e retorna.
    Repete até encontrar nó que não seja mensagem/timer ou que tenha 0 ou mais de uma aresta.
    """
    for _ in range(max_steps):
        state.refresh_from_db()
        current = (
            FlowNode.objects.filter(pk=state.current_node_id)
            .select_related("flow")
            .first()
        )
        if not current:
            break
        if current.node_type != FlowNode.NODE_TYPE_MESSAGE:
            break
        edge = _get_single_next_edge(current)
        if not edge or not edge.to_node_id:
            break
        next_node = edge.to_node
        state.current_node_id = edge.to_node_id
        state.save(update_fields=["current_node_id"])

        if next_node.node_type == FlowNode.NODE_TYPE_DELAY:
            sec = (getattr(next_node, "delay_seconds", None) or 0)
            if sec < 1:
                sec = 1
            logger.info("[FLOW] Timer de %s s agendado, nó %s conversation=%s", sec, next_node.name, conversation.id)
            t = threading.Thread(
                target=_run_delay_advance,
                args=(str(conversation.id), str(next_node.id), sec),
                daemon=True,
            )
            t.start()
            return
        sent = send_flow_node(conversation, next_node)
        if not sent:
            break
        logger.info("[FLOW] Auto-advance (mensagem) para nó %s conversation=%s", next_node.name, conversation.id)


def process_flow_reply(conversation: Conversation, message: Message) -> bool:
    """
    Processa resposta a lista/botão ou texto quando a conversa está em um fluxo.
    - Lista/botão: option_id vem de list_reply/button_reply no metadata.
    - Nó tipo mensagem: option_id é o texto enviado pelo usuário (comparado ao option_id da aresta).
    Transições: próximo nó (to_node), transferir para departamento, ou encerrar.
    Retorna True se processou (e não deve processar Welcome Menu); False caso contrário.
    Usa lock na mensagem para evitar processamento duplicado (race entre workers).
    """
    if not conversation or not message:
        return False
    if not getattr(message, "pk", None):
        return False

    meta = message.metadata or {}
    list_reply = meta.get("list_reply")
    button_reply = meta.get("button_reply")

    option_id = None
    if list_reply and isinstance(list_reply, dict):
        option_id = (list_reply.get("id") or "").strip()
    if not option_id and button_reply and isinstance(button_reply, dict):
        option_id = (button_reply.get("id") or "").strip()

    try:
        with transaction.atomic():
            # Lock da mensagem para evitar dois workers processarem a mesma resposta
            try:
                msg_locked = Message.objects.select_for_update().filter(pk=message.pk).first()
            except Exception:
                msg_locked = None
            if not msg_locked:
                return False
            meta = dict(msg_locked.metadata or {})
            if meta.get("flow_reply_processed"):
                return True

            state = ConversationFlowState.objects.select_related("flow", "current_node").filter(
                conversation_id=conversation.id
            ).first()
            if not state:
                return False

            # Nó tipo mensagem: usar texto da resposta do usuário como gatilho (option_id)
            if not option_id and state.current_node_id:
                current = state.current_node
                if current and current.node_type == FlowNode.NODE_TYPE_MESSAGE:
                    option_id = (getattr(message, "content", None) or "").strip()
                if not option_id:
                    return False

            if not option_id:
                return False

            option_id_norm = _normalize_option_id(option_id)
            edges = list(
                FlowEdge.objects.select_related("to_node", "to_node__flow", "target_department").filter(
                    from_node_id=state.current_node_id
                )
            )
            edge = None
            for e in edges:
                if _normalize_option_id(e.option_id) == option_id_norm:
                    edge = e
                    break
            if not edge:
                logger.info("[FLOW] Opção inválida ou sem aresta: conversation=%s option_id=%s", conversation.id, option_id)
                return False

            # Marcar como processada antes de enviar para evitar reprocessamento em caso de falha após envio
            meta["flow_reply_processed"] = True
            msg_locked.metadata = meta
            msg_locked.save(update_fields=["metadata"])

            if edge.to_node_id:
                if not edge.to_node:
                    logger.warning("[FLOW] Aresta aponta para nó inexistente (removido?): edge=%s to_node_id=%s", edge.id, edge.to_node_id)
                    return False
                sent = send_flow_node(conversation, edge.to_node)
                if sent:
                    state.current_node_id = edge.to_node_id
                    state.save(update_fields=["current_node_id"])
                    logger.info("[FLOW] Avançou para nó %s conversation=%s", edge.to_node.name, conversation.id)
                    _auto_advance_message_chain(conversation, state)
                    return True
                return False

            if edge.target_department_id:
                from apps.chat.services.welcome_menu_service import WelcomeMenuService

                department = Department.objects.filter(id=edge.target_department_id).first()
                if department:
                    success = WelcomeMenuService._transfer_to_department(conversation, department)
                    state.delete()
                    logger.info("[FLOW] Transferido para %s conversation=%s", department.name, conversation.id)
                    return success
                logger.warning(
                    "[FLOW] Aresta aponta para departamento inexistente (removido?): edge=%s target_department_id=%s",
                    edge.id,
                    edge.target_department_id,
                )
                state.delete()
                return False

            if edge.target_action == FlowEdge.TARGET_ACTION_END:
                from apps.chat.services.welcome_menu_service import WelcomeMenuService

                success = WelcomeMenuService._close_conversation(conversation)
                state.delete()
                logger.info("[FLOW] Conversa encerrada conversation=%s", conversation.id)
                return success

            return False
    except Exception as e:
        logger.exception("[FLOW] Erro ao processar resposta do fluxo: %s", e)
        return False


def try_send_flow_start(conversation: Conversation, flow: Optional[Flow] = None):
    """
    Se existir fluxo ativo para o escopo da conversa, envia o nó inicial e cria estado.
    flow: opcional; se informado, usa esse fluxo (deve ser ativo e do escopo da conversa).
    Respeita allow_meta_interactive_buttons do tenant (se desativado, não envia fluxo).
    Não envia se a conversa já estiver em um fluxo (evita reenviar nó inicial).
    Retorna (sent: bool, extra: dict). extra pode ter "messages_queued" (Typebot).
    """
    if not conversation or not conversation.tenant_id:
        return (False, {})
    if ConversationFlowState.objects.filter(conversation_id=conversation.id).exists():
        return (False, {})
    from apps.tenancy.models import Tenant
    allow = Tenant.objects.filter(id=conversation.tenant_id).values_list("allow_meta_interactive_buttons", flat=True).first()
    if allow is False:
        logger.info("[FLOW] Tenant desativou botões interativos, não enviando fluxo: tenant=%s", conversation.tenant_id)
        return (False, {})

    if flow is not None:
        # Validar que o fluxo é do escopo da conversa e está ativo
        allowed = get_active_flows_for_conversation(conversation).filter(id=flow.id).exists()
        if not allowed:
            flow = None
    if flow is None:
        flow = get_active_flow_for_conversation(conversation)
    if not flow:
        return (False, {})

    # Typebot: quando o fluxo tem typebot_public_id, executar via Typebot em vez de nós/arestas
    typebot_public_id = (getattr(flow, "typebot_public_id", None) or "").strip()
    if typebot_public_id:
        try:
            from apps.chat.services.typebot_flow_service import start_typebot_flow
            ok, messages_queued = start_typebot_flow(conversation, flow)
            if ok:
                logger.info("[FLOW] Fluxo Typebot iniciado: conversation=%s flow=%s messages_queued=%s", conversation.id, flow.name, messages_queued)
                return (True, {"messages_queued": messages_queued})
        except Exception as e:
            logger.exception("[FLOW] Erro ao iniciar Typebot: %s", e)
        return (False, {})

    start_node = get_start_node(flow)
    if not start_node:
        logger.warning("[FLOW] Fluxo sem nó inicial: %s", flow.id)
        return (False, {})

    # Criar estado primeiro (evita race: dois requests não enviam o nó inicial duas vezes)
    try:
        state, created = ConversationFlowState.objects.get_or_create(
            conversation_id=conversation.id,
            defaults={"flow_id": flow.id, "current_node_id": start_node.id},
        )
    except Exception as e:
        logger.exception("[FLOW] Erro ao criar ConversationFlowState: %s", e)
        return (False, {})

    if not created:
        return (False, {})  # Já estava em fluxo (outro request criou o estado)

    if start_node.node_type == FlowNode.NODE_TYPE_DELAY:
        sec = getattr(start_node, "delay_seconds", None) or 0
        if sec < 1:
            sec = 1
        logger.info("[FLOW] Fluxo iniciado com timer de %s s conversation=%s flow=%s", sec, conversation.id, flow.name)
        t = threading.Thread(
            target=_run_delay_advance,
            args=(str(conversation.id), str(start_node.id), sec),
            daemon=True,
        )
        t.start()
        return (True, {})

    message = send_flow_node(conversation, start_node)
    if not message:
        try:
            state.delete()
        except Exception:
            pass
        logger.warning("[FLOW] Falha ao enfileirar nó inicial; estado removido conversation=%s", conversation.id)
        return (False, {})

    _auto_advance_message_chain(conversation, state)
    logger.info("[FLOW] Fluxo iniciado conversation=%s flow=%s", conversation.id, flow.name)
    return (True, {})


def process_incoming_message_flows(conversation: Conversation, message: Message) -> bool:
    """
    Processa fluxo para mensagem incoming: Typebot (continueChat), fluxo Sense (lista/botão) ou menu de boas-vindas.
    Só roda se a conversa não estiver atribuída a um humano (assigned_to_id).
    Retorna True se algum fluxo foi processado.
    Usado pelo webhook Evolution e pelo webhook Meta (Cloud API) para manter o mesmo comportamento.
    """
    if not conversation or not message or conversation.assigned_to_id:
        return False
    if getattr(conversation, "status", None) == "closed":
        return False
    flow_processed = False
    try:
        state = ConversationFlowState.objects.filter(conversation_id=conversation.id).first()
        if state and ((getattr(state, "typebot_session_id", None) or "").strip()):
            from apps.chat.services.typebot_flow_service import continue_typebot_flow
            msg_content = (getattr(message, "content", None) or "").strip()
            if msg_content and continue_typebot_flow(conversation, msg_content):
                flow_processed = True
                logger.info("[FLOW] Resposta Typebot processada conversation=%s", conversation.id)
        if not flow_processed:
            flow_processed = process_flow_reply(conversation, message)
            if flow_processed:
                logger.info("[FLOW] Resposta do fluxo processada conversation=%s", conversation.id)
        if flow_processed:
            conversation.refresh_from_db()
        if not flow_processed:
            from apps.chat.services.welcome_menu_service import WelcomeMenuService
            if WelcomeMenuService.process_menu_response(conversation, message):
                flow_processed = True
                conversation.refresh_from_db()
                logger.info("[FLOW] Resposta do menu de boas-vindas processada conversation=%s", conversation.id)
    except Exception as e:
        logger.exception("[FLOW] Erro ao processar resposta do fluxo: %s", e)
    return flow_processed
