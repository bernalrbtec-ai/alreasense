"""
Motor de fluxo conversacional: processa respostas a lista/botões e envia próximas etapas.
Fluxo por Inbox ou departamento; coexistência com Welcome Menu.
"""
import logging
import re
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
    if not conversation or not conversation.tenant_id:
        return None
    if conversation.department_id is None:
        return Flow.objects.filter(
            tenant_id=conversation.tenant_id,
            scope=Flow.SCOPE_INBOX,
            is_active=True,
            department__isnull=True,
        ).first()
    return Flow.objects.filter(
        tenant_id=conversation.tenant_id,
        scope=Flow.SCOPE_DEPARTMENT,
        department_id=conversation.department_id,
        is_active=True,
    ).first()


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
    """Monta payload interactive_list a partir do nó (tipo list)."""
    return {
        "body_text": (node.body_text or "").strip()[:1024],
        "button_text": (node.button_text or "").strip()[:20],
        "header_text": (node.header_text or "").strip()[:60],
        "footer_text": (node.footer_text or "").strip()[:60],
        "sections": list(node.sections or [])[:10],
    }


def _build_interactive_buttons_payload(node: FlowNode) -> Dict[str, Any]:
    """Monta payload interactive_reply_buttons a partir do nó (tipo buttons)."""
    buttons = list(node.buttons or [])[:3]
    return {
        "body_text": (node.body_text or "").strip()[:1024],
        "buttons": [{"id": (b.get("id") or "").strip()[:100], "title": (b.get("title") or "").strip()[:20]} for b in buttons if isinstance(b, dict)],
    }


def send_flow_node(conversation: Conversation, node: FlowNode) -> Optional[Message]:
    """
    Cria mensagem com lista ou botões do nó e enfileira envio.
    Retorna a mensagem criada ou None.
    """
    from apps.chat.tasks import send_message_to_evolution

    if conversation.tenant_id != node.flow.tenant_id:
        logger.warning("[FLOW] Tenant da conversa não coincide com o do fluxo: conversation=%s node.flow=%s", conversation.id, node.flow_id)
        return None

    if node.node_type == FlowNode.NODE_TYPE_LIST:
        payload = _build_interactive_list_payload(node)
        if not payload.get("body_text") or not payload.get("button_text") or not payload.get("sections"):
            logger.warning("[FLOW] Nó lista inválido (body/button/sections): %s", node.id)
            return None
        content = payload["body_text"]
        metadata = {"interactive_list": payload, "flow_node_id": str(node.id), "flow_id": str(node.flow_id)}
    elif node.node_type == FlowNode.NODE_TYPE_BUTTONS:
        payload = _build_interactive_buttons_payload(node)
        if not payload.get("body_text") or not payload.get("buttons"):
            logger.warning("[FLOW] Nó botões inválido (body/buttons): %s", node.id)
            return None
        content = payload["body_text"]
        metadata = {"interactive_reply_buttons": payload, "flow_node_id": str(node.id), "flow_id": str(node.flow_id)}
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


def process_flow_reply(conversation: Conversation, message: Message) -> bool:
    """
    Processa resposta a lista/botão quando a conversa está em um fluxo.
    Retorna True se processou (e não deve processar Welcome Menu); False caso contrário.
    """
    meta = message.metadata or {}
    list_reply = meta.get("list_reply")
    button_reply = meta.get("button_reply")

    option_id = None
    if list_reply and isinstance(list_reply, dict):
        option_id = (list_reply.get("id") or "").strip()
    if not option_id and button_reply and isinstance(button_reply, dict):
        option_id = (button_reply.get("id") or "").strip()

    if not option_id:
        return False

    # Idempotência: não processar duas vezes
    if meta.get("flow_reply_processed"):
        return True

    try:
        state = ConversationFlowState.objects.select_related("flow", "current_node").filter(
            conversation_id=conversation.id
        ).first()
    except Exception:
        return False

    if not state:
        return False

    # Matching com option_id normalizado (Evolution devolve rowId sanitizado)
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

    if edge.to_node_id:
        if not edge.to_node:
            logger.warning("[FLOW] Aresta aponta para nó inexistente (removido?): edge=%s to_node_id=%s", edge.id, edge.to_node_id)
            return False
        sent = send_flow_node(conversation, edge.to_node)
        if sent:
            state.current_node_id = edge.to_node_id
            state.save(update_fields=["current_node_id"])
            try:
                m_meta = dict(message.metadata or {})
                m_meta["flow_reply_processed"] = True
                message.metadata = m_meta
                message.save(update_fields=["metadata"])
            except Exception as e:
                logger.warning("[FLOW] Falha ao marcar flow_reply_processed: %s", e)
            logger.info("[FLOW] Avançou para nó %s conversation=%s", edge.to_node.name, conversation.id)
            return True
        return False

    if edge.target_department_id:
        # Transferir para departamento
        from apps.chat.services.welcome_menu_service import WelcomeMenuService

        department = Department.objects.filter(id=edge.target_department_id).first()
        if department:
            success = WelcomeMenuService._transfer_to_department(conversation, department)
            state.delete()
            try:
                m_meta = dict(message.metadata or {})
                m_meta["flow_reply_processed"] = True
                message.metadata = m_meta
                message.save(update_fields=["metadata"])
            except Exception:
                pass
            logger.info("[FLOW] Transferido para %s conversation=%s", department.name, conversation.id)
            return success
        state.delete()
        return False

    if edge.target_action == FlowEdge.TARGET_ACTION_END:
        # Encerrar conversa
        from apps.chat.services.welcome_menu_service import WelcomeMenuService

        success = WelcomeMenuService._close_conversation(conversation)
        state.delete()
        try:
            m_meta = dict(message.metadata or {})
            m_meta["flow_reply_processed"] = True
            message.metadata = m_meta
            message.save(update_fields=["metadata"])
        except Exception:
            pass
        logger.info("[FLOW] Conversa encerrada conversation=%s", conversation.id)
        return success

    return False


def try_send_flow_start(conversation: Conversation) -> bool:
    """
    Se existir fluxo ativo para o escopo da conversa, envia o nó inicial e cria estado.
    Respeita allow_meta_interactive_buttons do tenant (se desativado, não envia fluxo).
    Não envia se a conversa já estiver em um fluxo (evita reenviar nó inicial).
    Retorna True se enviou fluxo; False para fallback para Welcome Menu.
    """
    if not conversation or not conversation.tenant_id:
        return False
    if ConversationFlowState.objects.filter(conversation_id=conversation.id).exists():
        return False
    from apps.tenancy.models import Tenant
    allow = Tenant.objects.filter(id=conversation.tenant_id).values_list("allow_meta_interactive_buttons", flat=True).first()
    if allow is False:
        logger.info("[FLOW] Tenant desativou botões interativos, não enviando fluxo: tenant=%s", conversation.tenant_id)
        return False

    flow = get_active_flow_for_conversation(conversation)
    if not flow:
        return False

    start_node = get_start_node(flow)
    if not start_node:
        logger.warning("[FLOW] Fluxo sem nó inicial: %s", flow.id)
        return False

    message = send_flow_node(conversation, start_node)
    if not message:
        return False

    try:
        ConversationFlowState.objects.get_or_create(
            conversation_id=conversation.id,
            defaults={"flow_id": flow.id, "current_node_id": start_node.id},
        )
    except Exception as e:
        logger.exception("[FLOW] Erro ao criar ConversationFlowState: %s", e)
        return False

    logger.info("[FLOW] Fluxo iniciado conversation=%s flow=%s", conversation.id, flow.name)
    return True
