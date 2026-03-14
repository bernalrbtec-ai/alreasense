"""
Plug LibreChat: resolução de agente por slug + tenant e chamada à API de agentes.
Retorno normalizado: {"ok": True, "reply_text": "..."} ou {"ok": False, "error": "..."}.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

from apps.ai.models import Agent

logger = logging.getLogger(__name__)

LIBRECHAT_TIMEOUT = 30
LIBRECHAT_RETRY_DELAY = 2
# Limite de reply_text retornado (evita payload gigante; a secretária pode truncar de novo)
LIBRECHAT_REPLY_MAX_LENGTH = 100_000


class AgentNotFoundError(Exception):
    """Agente não encontrado na resolução por slug + tenant."""


def _parse_error_response(resp: requests.Response) -> str:
    """Extrai mensagem de erro do corpo da resposta (4xx/5xx); evita AttributeError se error for string."""
    raw = (resp.text or "")[:500]
    try:
        body = resp.json()
    except (ValueError, TypeError):
        return raw or f"HTTP {resp.status_code}"
    if not isinstance(body, dict):
        return raw or f"HTTP {resp.status_code}"
    err = body.get("error")
    if isinstance(err, dict):
        return (err.get("message") or err.get("code") or raw) or f"HTTP {resp.status_code}"
    if isinstance(err, str):
        return err
    return raw or f"HTTP {resp.status_code}"


def resolve_agent(agent_slug: str, tenant_id: Optional[Any]) -> Optional[Agent]:
    """
    Resolve o agente por slug e tenant_id.
    Ordem: primeiro agente sistema (tenant_id nulo); se não existir, agente do tenant.
    """
    # 1) Agente sistema (tenant_id nulo)
    system_agent = Agent.objects.filter(slug=agent_slug, tenant_id__isnull=True).first()
    if system_agent is not None:
        return system_agent
    # 2) Agente do tenant
    if tenant_id is not None:
        return Agent.objects.filter(slug=agent_slug, tenant_id=tenant_id).first()
    return None


def _build_messages(
    context_messages: List[Dict[str, Any]],
    system_prompt_override: str = "",
    context_extra: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Converte mensagens do contexto da secretária para formato role/content (OpenAI/LibreChat).
    context_messages: lista de {direction, content, ...}; direction = incoming -> user, outgoing -> assistant.
    """
    messages: List[Dict[str, str]] = []
    system_parts = []
    if (system_prompt_override or "").strip():
        system_parts.append(system_prompt_override.strip())
    if context_extra:
        if isinstance(context_extra.get("prompt"), str) and context_extra["prompt"].strip():
            system_parts.append(context_extra["prompt"].strip())
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
    for msg in context_messages or []:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        direction = (msg.get("direction") or "").lower()
        role = "user" if direction == "incoming" else "assistant"
        messages.append({"role": role, "content": content})
    return messages


def librechat_chat(
    agent_slug: str,
    tenant_id: Optional[Any],
    messages: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Chama o LibreChat Agents API e retorna formato normalizado.
    Sempre retorna um dict: {"ok": True, "reply_text": "..."} ou {"ok": False, "error": "..."}.
    Com zero agentes ou agente sem librechat_agent_id: retorna ok=False com mensagem clara.
    """
    try:
        return _librechat_chat_impl(agent_slug, tenant_id, messages, context)
    except Exception as e:
        logger.warning("[LIBRECHAT] Erro inesperado: %s", e, exc_info=True)
        return {"ok": False, "error": str(e) if str(e) else "Erro inesperado no plug LibreChat."}


def _librechat_chat_impl(
    agent_slug: str,
    tenant_id: Optional[Any],
    messages: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base_url = (getattr(settings, "LIBRECHAT_URL", None) or "").strip().rstrip("/")
    api_key = (getattr(settings, "LIBRECHAT_API_KEY", None) or "").strip()
    if not base_url or not api_key:
        return {"ok": False, "error": "LibreChat não configurado (LIBRECHAT_URL ou LIBRECHAT_API_KEY vazio)."}
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return {"ok": False, "error": "LIBRECHAT_URL deve usar http:// ou https://."}
    agent = resolve_agent(agent_slug, tenant_id)
    if agent is None:
        return {"ok": False, "error": "Agente não encontrado."}
    agent_id = (agent.librechat_agent_id or "").strip()
    if not agent_id:
        return {"ok": False, "error": "Agente sem librechat_agent_id configurado."}
    # Montar final_messages: a partir do context (secretária) ou do parâmetro messages
    if context and "messages" in context and isinstance(context["messages"], list):
        system_override = (agent.system_prompt_override or "").strip()
        final_messages = _build_messages(
            context["messages"],
            system_prompt_override=system_override,
            context_extra=context,
        )
    else:
        if not messages:
            return {"ok": False, "error": "messages vazio."}
        system_override = (agent.system_prompt_override or "").strip()
        final_messages = list(messages)
        if system_override and final_messages and final_messages[0].get("role") != "system":
            final_messages.insert(0, {"role": "system", "content": system_override})
    # Não chamar a API sem mensagens (pelo menos uma user ou assistant)
    if not any((m if isinstance(m, dict) else {}).get("role") in ("user", "assistant") for m in final_messages):
        return {"ok": False, "error": "Nenhuma mensagem de usuário ou assistente para enviar."}
    url = f"{base_url}/api/agents/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": agent_id, "messages": final_messages, "stream": False}
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=LIBRECHAT_TIMEOUT)
            if resp.status_code >= 400:
                err_msg = _parse_error_response(resp)
                logger.warning(
                    "[LIBRECHAT] HTTP %s agent_slug=%s tenant_id=%s: %s",
                    resp.status_code, agent_slug, tenant_id, err_msg,
                )
                return {"ok": False, "error": err_msg}
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, TypeError):
                logger.warning("[LIBRECHAT] Resposta 200 mas corpo não é JSON válido")
                return {"ok": False, "error": "Resposta inválida do LibreChat (não-JSON)."}
            choices = data.get("choices") or []
            if not choices:
                return {"ok": False, "error": "Resposta sem choices."}
            msg = choices[0].get("message") or {}
            reply_text = (msg.get("content") or "").strip()
            if len(reply_text) > LIBRECHAT_REPLY_MAX_LENGTH:
                reply_text = reply_text[:LIBRECHAT_REPLY_MAX_LENGTH]
                logger.info("[LIBRECHAT] reply_text truncado a %s caracteres", LIBRECHAT_REPLY_MAX_LENGTH)
            return {"ok": True, "reply_text": reply_text}
        except requests.Timeout as e:
            last_error = e
            logger.warning("[LIBRECHAT] Timeout agent_slug=%s tenant_id=%s: %s", agent_slug, tenant_id, e)
        except requests.RequestException as e:
            last_error = e
            logger.warning("[LIBRECHAT] Request error agent_slug=%s tenant_id=%s: %s", agent_slug, tenant_id, e, exc_info=True)
        except (ValueError, TypeError) as e:
            last_error = e
            logger.warning("[LIBRECHAT] Erro ao processar resposta: %s", e, exc_info=True)
        if attempt == 0:
            time.sleep(LIBRECHAT_RETRY_DELAY)
    return {"ok": False, "error": str(last_error) if last_error else "Erro ao chamar LibreChat."}


def librechat_chat_with_agent_id(
    librechat_agent_id: str,
    messages: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None,
    system_prompt_override: str = "",
) -> Dict[str, Any]:
    """
    Chama o LibreChat com agent_id explícito (ex.: de AgentAssignment).
    Retorno igual a librechat_chat: {"ok": True, "reply_text": "..."} ou {"ok": False, "error": "..."}.
    """
    try:
        return _librechat_chat_impl_with_agent_id(
            librechat_agent_id, messages, context, system_prompt_override
        )
    except Exception as e:
        logger.warning("[LIBRECHAT] Erro inesperado (chat_with_agent_id): %s", e, exc_info=True)
        return {"ok": False, "error": str(e) if str(e) else "Erro inesperado no plug LibreChat."}


def _librechat_chat_impl_with_agent_id(
    agent_id: str,
    messages: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None,
    system_prompt_override: str = "",
) -> Dict[str, Any]:
    base_url = (getattr(settings, "LIBRECHAT_URL", None) or "").strip().rstrip("/")
    api_key = (getattr(settings, "LIBRECHAT_API_KEY", None) or "").strip()
    if not base_url or not api_key:
        return {"ok": False, "error": "LibreChat não configurado."}
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return {"ok": False, "error": "LIBRECHAT_URL deve usar http:// ou https://."}
    agent_id = (agent_id or "").strip()
    if not agent_id:
        return {"ok": False, "error": "librechat_agent_id vazio."}
    if context and "messages" in context and isinstance(context["messages"], list):
        final_messages = _build_messages(
            context["messages"],
            system_prompt_override=system_prompt_override or "",
            context_extra=context,
        )
    else:
        if not messages:
            return {"ok": False, "error": "messages vazio."}
        final_messages = list(messages)
        if system_prompt_override and final_messages and final_messages[0].get("role") != "system":
            final_messages.insert(0, {"role": "system", "content": system_prompt_override})
    if not any((m if isinstance(m, dict) else {}).get("role") in ("user", "assistant") for m in final_messages):
        return {"ok": False, "error": "Nenhuma mensagem de usuário ou assistente para enviar."}
    url = f"{base_url}/api/agents/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": agent_id, "messages": final_messages, "stream": False}
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=LIBRECHAT_TIMEOUT)
            if resp.status_code >= 400:
                err_msg = _parse_error_response(resp)
                logger.warning("[LIBRECHAT] HTTP %s agent_id=%s: %s", resp.status_code, agent_id, err_msg)
                return {"ok": False, "error": err_msg}
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, TypeError):
                return {"ok": False, "error": "Resposta inválida do LibreChat (não-JSON)."}
            choices = data.get("choices") or []
            if not choices:
                return {"ok": False, "error": "Resposta sem choices."}
            msg = choices[0].get("message") or {}
            reply_text = (msg.get("content") or "").strip()
            if len(reply_text) > LIBRECHAT_REPLY_MAX_LENGTH:
                reply_text = reply_text[:LIBRECHAT_REPLY_MAX_LENGTH]
            return {"ok": True, "reply_text": reply_text}
        except requests.Timeout as e:
            last_error = e
        except requests.RequestException as e:
            last_error = e
        except (ValueError, TypeError) as e:
            last_error = e
        if attempt == 0:
            time.sleep(LIBRECHAT_RETRY_DELAY)
    return {"ok": False, "error": str(last_error) if last_error else "Erro ao chamar LibreChat."}
