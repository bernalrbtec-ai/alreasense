"""
Integração com Typebot: execução de fluxos via API (startChat / continueChat).
Quando Flow.typebot_public_id está preenchido, o fluxo é executado pelo Typebot;
as mensagens retornadas pela API são enviadas ao WhatsApp via Message + send_message_to_evolution.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.db import transaction

from apps.chat.models import Conversation, Message
from apps.chat.models_flow import Flow, ConversationFlowState
from apps.chat.tasks import send_message_to_evolution

logger = logging.getLogger(__name__)

DEFAULT_TYPEBOT_BASE = "https://typebot.io/api/v1"


def _typebot_base_url(flow: Flow) -> str:
    base = (getattr(flow, "typebot_base_url", None) or "").strip().rstrip("/")
    if base:
        return f"{base}/api/v1" if "/api/v1" not in base else base
    return DEFAULT_TYPEBOT_BASE


def _typebot_public_id(flow: Flow) -> Optional[str]:
    pid = (getattr(flow, "typebot_public_id", None) or "").strip()
    return pid or None


def _extract_text_from_messages(data: dict) -> List[str]:
    """Extrai textos da lista 'messages' da resposta do Typebot (startChat ou continueChat)."""
    messages = data.get("messages") if isinstance(data.get("messages"), list) else []
    texts = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("type") == "text":
            content = m.get("content")  # pode ser string ou richText (objeto)
            if isinstance(content, str) and content.strip():
                texts.append(content.strip())
            elif isinstance(content, dict) and content.get("richText"):
                # richText é array de blocos; simplificar para texto plano
                rt = content.get("richText")
                if isinstance(rt, list):
                    parts = []
                    for block in rt:
                        if isinstance(block, dict) and "content" in block:
                            for c in block.get("content", []) if isinstance(block.get("content"), list) else []:
                                if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                                    parts.append(str(c.get("text", "")))
                        elif isinstance(block, dict) and block.get("text"):
                            parts.append(str(block["text"]))
                    if parts:
                        texts.append("\n".join(parts))
            elif content:
                texts.append(str(content).strip())
    return texts


def _send_texts_to_whatsapp(conversation: Conversation, texts: List[str], metadata: Optional[dict] = None) -> None:
    """Cria uma Message por texto e enfileira envio para Evolution/Meta."""
    if not conversation or not texts:
        return
    meta = dict(metadata or {})
    meta["flow_engine"] = "typebot"
    for content in texts:
        if not (content and str(content).strip()):
            continue
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=content,
                    direction="outgoing",
                    status="pending",
                    is_internal=False,
                    metadata=meta,
                )
                transaction.on_commit(lambda msg_id=message.id: send_message_to_evolution.delay(str(msg_id)))
            logger.info("[TYPEBOT] Mensagem enfileirada conversation=%s", conversation.id)
        except Exception as e:
            logger.exception("[TYPEBOT] Erro ao criar/enfileirar mensagem: %s", e)


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
    # Garantir nomes padrão se ainda não definidos
    if "NomeContato" not in prefilled:
        prefilled["NomeContato"] = prefilled.get("contact_name") or "Contato"
    if "NumeroFone" not in prefilled:
        prefilled["NumeroFone"] = prefilled.get("contact_phone") or ""
    extra = getattr(flow, "typebot_prefilled_extra", None)
    if isinstance(extra, dict) and extra:
        for k, v in extra.items():
            if k and isinstance(v, (str, int, float, bool)):
                prefilled[str(k).strip()] = str(v)
            elif k and v is not None:
                prefilled[str(k).strip()] = str(v)
    payload = {"prefilledVariables": prefilled}
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
            state, created = ConversationFlowState.objects.update_or_create(
                conversation_id=conversation.id,
                defaults={
                    "flow_id": flow.id,
                    "current_node_id": None,
                    "typebot_session_id": session_id,
                },
            )
            result_id = (data.get("resultId") or "").strip()
            if result_id:
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
    flow = state.flow
    if not _typebot_public_id(flow):
        return False
    base = _typebot_base_url(flow)
    url = f"{base}/sessions/{state.typebot_session_id}/continueChat"
    payload = {"message": {"type": "text", "content": user_message}}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("[TYPEBOT] continueChat falhou: %s", e)
        return False
    texts = _extract_text_from_messages(data)
    _send_texts_to_whatsapp(conversation, texts)
    # Se o Typebot retornar um "input" (próximo bloco de pergunta), a sessão continua.
    # Se não houver input, opcionalmente podemos limpar a sessão ou mantê-la para histórico.
    logger.info("[TYPEBOT] continueChat processado conversation=%s messages=%s", conversation.id, len(texts))
    return True
