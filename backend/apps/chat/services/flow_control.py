"""
Controle universal de automações por instruções embutidas em texto.

Formato suportado:
  #{"closeTicket": true}
  #{"transferTo": "Departamento"}

Objetivo:
- Reaproveitar o mesmo parser/ações para múltiplos motores (Typebot, Dify, etc.)
- Executar ações (encerrar, transferir) e remover o trecho de instrução do texto
  antes de enviar ao cliente.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from django.db import transaction

from apps.chat.models import Conversation, Message

logger = logging.getLogger(__name__)

# Limite de leitura para evitar scans/carregamentos caros e payloads maliciosos
MAX_INSTRUCTION_JSON_LENGTH = 500

# Chaves reconhecidas no JSON da instrução
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


def close_conversation_from_bot(conversation: Conversation, source: str = "bot") -> bool:
    """
    Fecha a conversa:
    - marca mensagens incoming como seen
    - status=closed, department/assigned_to=None
    - limpa ConversationFlowState (se existir)
    """
    if not conversation or getattr(conversation, "status", None) == "closed":
        return True
    try:
        from apps.chat.models_flow import ConversationFlowState

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
        logger.info("[%s] Conversa %s fechada por instrução", (source or "bot").upper(), conversation.id)
        return True
    except Exception as exc:
        logger.warning(
            "[%s] Erro ao fechar conversa por instrução: %s",
            (source or "bot").upper(),
            exc,
            exc_info=True,
        )
        return False


def transfer_conversation_to_department(conversation: Conversation, department_name: str, source: str = "bot") -> bool:
    """Transfere conversa para o departamento identificado pelo nome (tenant + name__iexact)."""
    if not conversation or not getattr(conversation, "tenant_id", None):
        return False
    name = (department_name if isinstance(department_name, str) else str(department_name)).strip()
    if not name:
        return False
    try:
        from apps.authn.models import Department
        from apps.chat.models_flow import ConversationFlowState

        dept = Department.objects.filter(
            tenant_id=conversation.tenant_id,
            name__iexact=name,
        ).first()
        if not dept:
            logger.warning(
                "[%s] Departamento não encontrado por nome: %r conversation=%s",
                (source or "bot").upper(),
                name,
                conversation.id,
            )
            return False

        old_department = conversation.department
        with transaction.atomic():
            conversation.department = dept
            conversation.assigned_to = None
            conversation.status = "open"
            conversation.save(update_fields=["department", "assigned_to", "status"])
            ConversationFlowState.objects.filter(conversation_id=conversation.id).delete()

        old_name = old_department.name if old_department else "Inbox"
        transfer_msg = (
            f"Conversa transferida:\n"
            f"De: {old_name} (Não atribuído)\n"
            f"Para: {dept.name} (Não atribuído)\n"
            f"(por {(source or 'bot').capitalize()})"
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

        # Mensagem ao cliente (quando houver transfer_message do dept).
        # Importante: padronizar com o fluxo normal do chat (Message + fila de envio),
        # para manter histórico/status consistente e evitar envios "fora do sistema".
        transfer_message_text = (getattr(dept, "transfer_message", None) or "").strip()
        if not transfer_message_text:
            transfer_message_text = (
                f"Sua conversa foi transferida para o departamento {dept.name}. Em breve você será atendido."
            )

        try:
            from apps.chat.tasks import send_message_to_evolution
            from apps.chat.utils.websocket import broadcast_message_received

            meta: dict = {"source": source or "bot", "flow_engine": source or "bot"}
            with transaction.atomic():
                out_msg = Message.objects.create(
                    conversation=conversation,
                    sender=None,
                    content=transfer_message_text,
                    direction="outgoing",
                    status="pending",
                    is_internal=False,
                    metadata=meta,
                )
                out_id = str(out_msg.id)
                transaction.on_commit(lambda: send_message_to_evolution.delay(out_id))
            try:
                broadcast_message_received(out_msg)
            except Exception as ws_exc:
                logger.warning(
                    "[%s] Transferência OK; falha ao broadcast via WebSocket (não crítico): %s",
                    (source or "bot").upper(),
                    ws_exc,
                )
        except Exception as exc:
            logger.warning(
                "[%s] Transferência OK; erro ao resolver/enviar mensagem ao cliente: %s",
                (source or "bot").upper(),
                exc,
                exc_info=True,
            )

        conversation.refresh_from_db()
        logger.info("[%s] Transferência por instrução: conversation=%s -> %s", (source or "bot").upper(), conversation.id, dept.name)
        return True
    except Exception as exc:
        logger.warning(
            "[%s] Erro ao transferir por nome: %s",
            (source or "bot").upper(),
            exc,
            exc_info=True,
        )
        return False


def process_bot_control_instruction_single(
    conversation: Conversation,
    text: str,
    source: str = "bot",
) -> tuple[str, dict]:
    """
    Processa um único texto, executando no máximo uma ação de controle (close/transfer).
    Retorna (texto_limpo, meta).

    meta:
      - recognized: bool
      - closed: bool
      - transferred: bool
      - transfer_to: str | None
    """
    meta = {"recognized": False, "closed": False, "transferred": False, "transfer_to": None}
    if not conversation or not text:
        return ("" if not isinstance(text, str) else text), meta
    if not isinstance(text, str):
        return (str(text).strip(), meta)
    if not getattr(conversation, "tenant_id", None):
        return (text.strip(), meta)

    cleaned = text.strip()
    if not cleaned:
        return "", meta

    pos = 0
    while pos < len(cleaned):
        idx = cleaned.find("#{", pos)
        if idx < 0:
            break
        end = _find_matching_brace(cleaned, idx + 1)
        if end < 0:
            pos = idx + 2
            continue
        segment = cleaned[idx + 1 : end + 1].strip()[:MAX_INSTRUCTION_JSON_LENGTH]
        pos = end + 1
        try:
            obj = json.loads(segment)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue

        # 1) close
        for key in CLOSE_KEYS:
            if key in obj and obj[key]:
                meta["recognized"] = True
                meta["closed"] = True
                close_conversation_from_bot(conversation, source=source)
                before = cleaned[:idx].rstrip()
                after = cleaned[pos:].lstrip()
                cleaned = f"{before}\n{after}".strip() if before and after else (before or after)
                return (cleaned.strip(), meta)

        # 2) transfer
        for key in TRANSFER_KEYS:
            if key in obj:
                val = obj[key]
                name = (val if isinstance(val, str) else str(val)).strip() if val is not None else ""
                if name:
                    meta["recognized"] = True
                    meta["transferred"] = True
                    meta["transfer_to"] = name
                    transfer_conversation_to_department(conversation, name, source=source)
                before = cleaned[:idx].rstrip()
                after = cleaned[pos:].lstrip()
                cleaned = f"{before}\n{after}".strip() if before and after else (before or after)
                return (cleaned.strip(), meta)

    return (cleaned.strip(), meta)


def process_bot_control_instructions(
    conversation: Conversation,
    texts: Iterable[Any],
    source: str = "bot",
) -> list[str]:
    """
    Processa uma lista/batch de textos:
    - Executa instruções e remove trechos reconhecidos
    - Após um close, não processa mais instruções no restante do batch (comportamento Typebot)
    """
    if not conversation:
        return []
    if not isinstance(texts, (list, tuple)):
        return []
    if not getattr(conversation, "tenant_id", None):
        return [str(t).strip() for t in texts if t is not None and str(t).strip()]

    cleaned: list[str] = []
    closed = False
    for raw in texts:
        if raw is None:
            continue
        if not isinstance(raw, str):
            s = str(raw).strip()
            if s:
                cleaned.append(s)
            continue

        txt = raw.strip()
        if not txt:
            continue

        if closed:
            cleaned.append(txt)
            continue

        new_txt, meta = process_bot_control_instruction_single(conversation, txt, source=source)
        if meta.get("closed"):
            closed = True
        if new_txt and new_txt.strip():
            cleaned.append(new_txt.strip())
    return cleaned

