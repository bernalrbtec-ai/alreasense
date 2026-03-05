"""
Serviço da Secretária IA: contexto RAG (source=secretary), upsert ao ativar perfil,
construção de contexto para o gateway (RAG + memória por contato), worker assíncrono no Inbox.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai.embeddings import embed_text
from apps.ai.models import (
    AiGatewayAudit,
    AiKnowledgeDocument,
    AiMemoryItem,
    TenantAiSettings,
    TenantSecretaryProfile,
)
from apps.ai.vector_store import search_knowledge, search_memory_for_contact

logger = logging.getLogger(__name__)


def _server_time_utc_iso() -> str:
    """Data/hora atual em UTC (ISO 8601). Enviada em todos os payloads ao n8n para o fluxo não perder contexto de tempo."""
    return datetime.now(timezone.utc).isoformat()


def _build_system_data_block(
    tenant_name: str,
    business_hours: Dict[str, Any],
    server_time_utc: str,
) -> str:
    """
    Bloco com dados reais do sistema. Colocado NO INÍCIO do prompt para o modelo
    ver primeiro e não ignorar (nome da empresa, data/hora atual, grade de horário, status).
    """
    name = (tenant_name or "").strip() or "(nome não definido)"
    is_open = business_hours.get("is_open", True)
    status_msg = (business_hours.get("status_message") or "").strip()
    if not status_msg:
        status_msg = "ABERTA" if is_open else "FECHADA"
    lines = [
        "=== DADOS DO SISTEMA (OBRIGATÓRIO: use exatamente; não invente nem traduza) ===",
        f"Nome da empresa: {name}",
        f"Data/hora atual do servidor (UTC): {server_time_utc}",
    ]
    current_dt = business_hours.get("current_datetime_readable")
    if current_dt:
        lines.append(f"Data/hora atual (use para responder 'hoje é X', 'agora são Y'): {current_dt}")
    schedule = business_hours.get("schedule_text")
    if schedule:
        lines.append(f"Grade de horário de atendimento: {schedule}")
    lines.extend([
        f"Horário de atendimento agora: {status_msg}",
        f"is_open: {str(is_open).lower()}",
        "=== FIM DOS DADOS DO SISTEMA ===\n",
    ])
    return "\n".join(lines) + "\n"


SOURCE_SECRETARY = "secretary"
SECRETARY_N8N_TIMEOUT = 20
SECRETARY_N8N_RETRY_DELAY = 2
SECRETARY_TYPING_DELAY_SECONDS = 8  # Tempo que o indicador "digitando" fica ativo


def _apply_prompt_name_variable(prompt_text: str, signature_name: Optional[str]) -> str:
    """Substitui {{nome}} no prompt pelo nome da secretária (ex: no prompt do usuário)."""
    if not prompt_text:
        return prompt_text
    name = (signature_name or "").strip() or "Assistente"
    return prompt_text.replace("{{nome}}", name)


def build_secretary_context_text(form_data: Dict[str, Any]) -> str:
    """
    Monta o texto de contexto a partir do form_data do perfil (empresa).
    Usado como conteúdo do documento RAG e para embedding.
    """
    if not form_data:
        return ""
    parts = []
    for key, value in form_data.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value = " | ".join(str(x) for x in value)
        else:
            value = str(value)
        key_label = key.replace("_", " ").strip().title()
        parts.append(f"{key_label}: {value}")
    return "\n\n".join(parts)


def upsert_secretary_rag_for_tenant(tenant_id: str) -> None:
    """
    Atualiza o documento RAG da secretária para o tenant: remove documentos
    existentes com source='secretary' e cria um novo com o form_data atual.
    Embedding gerado aqui (ao salvar/ativar), não na hora da mensagem.
    """
    try:
        profile = TenantSecretaryProfile.objects.filter(tenant_id=tenant_id).first()
        if not profile or not profile.form_data:
            # Remove qualquer documento órfão
            AiKnowledgeDocument.objects.filter(tenant_id=tenant_id, source=SOURCE_SECRETARY).delete()
            return

        text = build_secretary_context_text(profile.form_data)
        if not text.strip():
            AiKnowledgeDocument.objects.filter(tenant_id=tenant_id, source=SOURCE_SECRETARY).delete()
            return

        embedding = embed_text(text)
        with transaction.atomic():
            AiKnowledgeDocument.objects.filter(
                tenant_id=tenant_id,
                source=SOURCE_SECRETARY,
            ).delete()
            AiKnowledgeDocument.objects.create(
                tenant_id=tenant_id,
                title="Secretária IA - Dados da empresa",
                content=text,
                source=SOURCE_SECRETARY,
                tags=[],
                metadata={},
                embedding=embedding or None,
            )
        logger.info(
            "[SECRETARY RAG] Salvamento OK para tenant %s: 1 doc, %s caracteres, embedding=%s",
            tenant_id,
            len(text),
            "ok" if embedding else "vazio",
        )
    except Exception as e:
        logger.exception("Secretary RAG upsert failed for tenant %s: %s", tenant_id, e)
        raise


def get_secretary_rag_context(
    tenant_id: str,
    query_embedding: List[float],
    limit: int = 5,
    similarity_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Busca conhecimento apenas source=secretary para o tenant.
    Usa threshold 0.5 para não descartar o doc "Dados da empresa".
    Se a busca semântica retornar vazio, faz fallback: retorna o(s) doc(s) da secretária
    para o modelo sempre ter o contexto da empresa.
    """
    items = search_knowledge(
        tenant_id=tenant_id,
        query_embedding=query_embedding,
        limit=limit,
        similarity_threshold=similarity_threshold,
        source=SOURCE_SECRETARY,
    )
    if items:
        return items
    # Fallback: garantir que o contexto "Dados da empresa" vá no payload quando existir
    fallback = list(
        AiKnowledgeDocument.objects.filter(
            tenant_id=tenant_id,
            source=SOURCE_SECRETARY,
            embedding__isnull=False,
        )
        .order_by("-created_at")[:limit]
        .values("id", "title", "content", "source", "tags", "metadata")
    )
    if fallback:
        logger.info(
            "[SECRETARY RAG] Busca semântica retornou 0; usando fallback com %s doc(s) para tenant %s",
            len(fallback),
            tenant_id,
        )
    return [
        {
            "id": str(d["id"]),
            "title": d["title"] or "",
            "content": d["content"] or "",
            "source": d["source"] or SOURCE_SECRETARY,
            "tags": d["tags"] or [],
            "metadata": d["metadata"] or {},
            "similarity": 1.0,
        }
        for d in fallback
    ]


def get_secretary_memory_for_contact(
    tenant_id: str,
    contact_phone: str,
    query_embedding: List[float],
    use_memory: bool = True,
    within_days: int = 365,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retorna memória do contato para a secretária (hierarquia tenant → contato → 1 ano).
    Se use_memory for False, retorna lista vazia (LGPD).
    """
    if not use_memory or not contact_phone:
        return []
    return search_memory_for_contact(
        tenant_id=tenant_id,
        contact_phone=contact_phone,
        query_embedding=query_embedding,
        within_days=within_days,
        limit=limit,
    )


def _resolve_n8n_ai_url(tenant) -> str:
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=tenant).first()
        if settings_obj and settings_obj.n8n_ai_webhook_url:
            return settings_obj.n8n_ai_webhook_url
    except Exception:
        pass
    return getattr(settings, "N8N_AI_WEBHOOK", "")


def _message_content_for_secretary(msg) -> str:
    """
    Conteúdo de uma mensagem para o contexto da secretária: texto, transcrição de áudio ou placeholder de mídia.
    Usa msg.content se preenchido; senão, anexos de áudio com transcription; se áudio sem transcrição, placeholder;
    se só imagem/vídeo (sem texto), devolve "[Imagem]" ou "[Vídeo]" para a BIA orientar encaminhamento.
    """
    text = (getattr(msg, "content", None) or "").strip()
    if text:
        return text
    attachments = getattr(msg, "attachments", None)
    if not attachments:
        return ""
    att_list = list(attachments.all())
    audio_attachments = [a for a in att_list if (getattr(a, "mime_type", "") or "").lower().find("audio") >= 0]
    image_attachments = [a for a in att_list if (getattr(a, "mime_type", "") or "").lower().startswith("image/")]
    video_attachments = [a for a in att_list if (getattr(a, "mime_type", "") or "").lower().startswith("video/")]
    if audio_attachments:
        transcriptions = []
        for a in audio_attachments:
            t = (getattr(a, "transcription", None) or "").strip()
            if t:
                transcriptions.append(t)
        if transcriptions:
            return "[Áudio] " + (" ".join(transcriptions) if len(transcriptions) > 1 else transcriptions[0])
        return "[Áudio em processamento]"
    if image_attachments or video_attachments:
        if image_attachments and not video_attachments:
            return "[Imagem]"
        if video_attachments and not image_attachments:
            return "[Vídeo]"
        return "[Imagem e vídeo]"
    return ""


def _build_secretary_context(conversation, message, profile: TenantSecretaryProfile) -> Dict[str, Any]:
    """Monta contexto para a Secretária: mensagens recentes (texto ou transcrição), RAG source=secretary, memória por contato."""
    from apps.chat.services.business_hours_service import BusinessHoursService
    from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag

    message_limit = getattr(settings, "AI_CONTEXT_MESSAGE_LIMIT", 20)
    recent_messages = list(
        conversation.messages.prefetch_related("attachments").order_by("-created_at")[:message_limit]
    )
    recent_messages.reverse()
    context_messages = []
    for msg in recent_messages:
        content = _message_content_for_secretary(msg)
        if content:
            context_messages.append({
                "id": str(msg.id),
                "direction": msg.direction,
                "content": content,
                "created_at": msg.created_at.isoformat(),
                "sender_name": getattr(msg, "sender_name", "") or "",
            })
    # Garantir que a mensagem que disparou a secretária seja a última (usar prefetched se for a mesma)
    trigger_msg = recent_messages[-1] if recent_messages and str(recent_messages[-1].id) == str(message.id) else message
    current_msg_content = _message_content_for_secretary(trigger_msg) or (message.content or "").strip()
    if current_msg_content:
        last_id = context_messages[-1]["id"] if context_messages else None
        if last_id != str(message.id):
            context_messages.append({
                "id": str(message.id),
                "direction": message.direction,
                "content": current_msg_content,
                "created_at": message.created_at.isoformat(),
                "sender_name": getattr(message, "sender_name", "") or "",
            })
    business_hours_obj = BusinessHoursService.get_business_hours(
        conversation.tenant, conversation.department
    )
    is_open, next_open_time = BusinessHoursService.is_business_hours(
        conversation.tenant, conversation.department
    )
    schedule_text = BusinessHoursService.format_schedule_text(business_hours_obj)
    tz_name = (getattr(business_hours_obj, "timezone", None) if business_hours_obj else None) or "America/Sao_Paulo"
    try:
        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now.astimezone(ZoneInfo(tz_name))
        day_names_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        current_datetime_readable = f"{day_names_pt[local_dt.weekday()]}, {local_dt.strftime('%d/%m/%Y')}, {local_dt.strftime('%H:%M')}"
    except Exception as e:
        logger.debug("[SECRETARY] Data/hora legível (timezone=%s): %s", tz_name, e)
        current_datetime_readable = ""
    # Log detalhado para debug de timezone
    from django.utils import timezone as django_timezone
    utc_now_django = django_timezone.now()
    logger.info(
        "[SECRETARY] Business hours check: is_open=%s, next_open_time=%s, UTC_now=%s",
        is_open,
        next_open_time,
        utc_now_django.strftime('%Y-%m-%d %H:%M:%S %Z'),
    )
    query_text = current_msg_content if current_msg_content else (message.content or "").strip()
    query_embedding = embed_text(query_text) if query_text else []
    knowledge_items = get_secretary_rag_context(
        str(conversation.tenant_id),
        query_embedding,
        limit=getattr(settings, "AI_RAG_TOP_K", 5),
    )
    logger.info(
        "[SECRETARY RAG] Consulta: tenant=%s knowledge_items=%s (query_len=%s)",
        conversation.tenant_id,
        len(knowledge_items),
        len(query_text),
    )
    if not knowledge_items:
        logger.warning(
            "[SECRETARY RAG] Nenhum item retornado para tenant %s; confira se o perfil está ativo e Dados da empresa foram salvos.",
            conversation.tenant_id,
        )
    memory_items = get_secretary_memory_for_contact(
        str(conversation.tenant_id),
        (conversation.contact_phone or "").strip(),
        query_embedding,
        use_memory=profile.use_memory,
        within_days=365,
        limit=getattr(settings, "AI_MEMORY_TOP_K", 5),
    )
    departments = []
    try:
        from apps.authn.models import Department
        for dept in Department.objects.filter(tenant=conversation.tenant).order_by("name"):
            departments.append({
                "id": str(dept.id),
                "name": dept.name,
                "routing_keywords": getattr(dept, "routing_keywords", []) or [],
            })
    except Exception:
        pass
    settings_obj = TenantAiSettings.objects.filter(tenant=conversation.tenant).first()
    # BIA: secretary_model se preenchido; senão agent_model; senão fallback fixo (evitar que payload vá sem model).
    secretary_model = (
        (getattr(settings_obj, "secretary_model", None) or "").strip()
        or (getattr(settings_obj, "agent_model", None) or "llama3.2")
    )
    prompt = (getattr(profile, "prompt", None) or "").strip()
    
    # ✅ MELHORIA: Incluir informação de horário de forma explícita no contexto
    business_hours_info = {
        "is_open": is_open,
        "next_open_time": next_open_time,
        "status_text": "ABERTA" if is_open else "FECHADA",
        "status_message": (
            f"A empresa está ABERTA no momento. Atenda normalmente."
            if is_open
            else (
                f"A empresa está FECHADA no momento."
                + (f" Retornamos em: {next_open_time}" if next_open_time else "")
            )
        ),
        "schedule_text": schedule_text,
        "current_datetime_readable": current_datetime_readable,
    }

    # company_context: fallback para n8n quando pgvector estiver vazio (BIA)
    company_context = ""
    try:
        from apps.tenancy.models import TenantCompanyProfile
        from apps.tenancy.rag_sync import _build_company_chunk
        profile_company = TenantCompanyProfile.objects.filter(tenant_id=conversation.tenant_id).first()
        if profile_company:
            company_context = _build_company_chunk(profile_company) or ""
    except Exception:
        pass

    contact_phone_raw = (conversation.contact_phone or "").strip()
    contact_phone_normalized = normalize_contact_phone_for_rag(contact_phone_raw)

    # Último departamento que atendeu o contato e data do último contato (para a secretária sugerir)
    last_department_name = conversation.department.name if conversation.department else None
    last_department_id = str(conversation.department_id) if conversation.department_id else None
    last_contact_dt = None
    if recent_messages:
        last_contact_dt = recent_messages[-1].created_at
    elif conversation.updated_at:
        last_contact_dt = conversation.updated_at
    else:
        last_contact_dt = message.created_at
    last_contact_date_iso = last_contact_dt.isoformat() if last_contact_dt else None
    try:
        last_contact_date_readable = last_contact_dt.strftime("%d/%m/%Y %H:%M") if last_contact_dt else None
    except Exception:
        last_contact_date_readable = last_contact_date_iso

    server_time_utc = _server_time_utc_iso()
    tenant_name = getattr(conversation.tenant, "name", "") or ""
    prompt_with_data = _build_system_data_block(
        tenant_name, business_hours_info, server_time_utc
    ) + (prompt or "").strip()
    if last_department_name or last_contact_date_readable:
        contact_context_lines = [
            "",
            "=== CONTATO (use para sugerir departamento ou referência ao último atendimento) ===",
        ]
        if last_department_name:
            contact_context_lines.append(f"Último departamento que atendeu o contato: {last_department_name}.")
        if last_contact_date_readable:
            contact_context_lines.append(f"Data do último contato: {last_contact_date_readable}.")
        contact_context_lines.append("=== FIM ===\n")
        prompt_with_data = prompt_with_data + "\n".join(contact_context_lines)
    # Instrução: ao encaminhar, a IA deve incluir obrigatoriamente o resumo na mesma linha
    prompt_with_data = prompt_with_data + "\n\nAo encaminhar (SUGERIR_DEPARTAMENTO), inclua obrigatoriamente na mesma linha: RESUMO_PARA_DEPARTAMENTO: <resumo em uma frase>."
    # Variável {{nome}} no prompt: substituir pelo nome da secretária
    signature_name = getattr(profile, "signature_name", None) or ""
    prompt_with_data = _apply_prompt_name_variable(prompt_with_data, signature_name)

    return {
        "agent_type": "secretary",
        "use_memory": getattr(profile, "use_memory", False),
        "server_time_utc": server_time_utc,
        "tenant": {"id": str(conversation.tenant_id), "name": tenant_name},
        "business_hours": business_hours_info,
        "company_context": company_context,
        "conversation": {
            "id": str(conversation.id),
            "status": conversation.status,
            "contact_name": conversation.contact_name,
            "contact_phone": contact_phone_raw,
            "contact_phone_normalized": contact_phone_normalized,
            "department": last_department_name,
            "department_id": last_department_id,
            "last_department_name": last_department_name,
            "last_department_id": last_department_id,
            "last_contact_date": last_contact_date_iso,
            "last_contact_date_readable": last_contact_date_readable,
        },
        "message": {
            "id": str(message.id),
            "direction": message.direction,
            "content": query_text or (message.content or ""),
            "created_at": message.created_at.isoformat(),
        },
        "messages": context_messages,
        "knowledge_items": knowledge_items,
        "memory_items": memory_items,
        "departments": departments,
        "model": secretary_model,
        "metadata": {"model": secretary_model},
        "prompt": prompt_with_data,
    }


def build_secretary_payload_for_test(
    tenant,
    message_text: str,
    messages_list: List[Dict[str, Any]],
    prompt: str,
    model: str,
    conversation_id: str,
    message_id: str,
    request_id: str,
    trace_id: str,
    signature_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Monta o payload no mesmo formato da produção (action=secretary) para o teste
    da área de Configuração da BIA. Inclui business_hours, company_context,
    knowledge_items (RAG), departments; conversa é isolada (messages_list).
    """
    from apps.chat.services.business_hours_service import BusinessHoursService
    from apps.tenancy.models import TenantCompanyProfile
    from apps.tenancy.rag_sync import _build_company_chunk

    tenant_id = str(tenant.id)
    business_hours_obj = BusinessHoursService.get_business_hours(tenant, department=None)
    is_open, next_open_time = BusinessHoursService.is_business_hours(tenant, department=None)
    schedule_text = BusinessHoursService.format_schedule_text(business_hours_obj)
    tz_name = (getattr(business_hours_obj, "timezone", None) if business_hours_obj else None) or "America/Sao_Paulo"
    try:
        utc_now = datetime.now(timezone.utc)
        local_dt = utc_now.astimezone(ZoneInfo(tz_name))
        day_names_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        current_datetime_readable = f"{day_names_pt[local_dt.weekday()]}, {local_dt.strftime('%d/%m/%Y')}, {local_dt.strftime('%H:%M')}"
    except Exception as e:
        logger.debug("[SECRETARY TEST] Data/hora legível (timezone=%s): %s", tz_name, e)
        current_datetime_readable = ""
    business_hours_info = {
        "is_open": is_open,
        "next_open_time": next_open_time,
        "status_text": "ABERTA" if is_open else "FECHADA",
        "status_message": (
            "A empresa está ABERTA no momento. Atenda normalmente."
            if is_open
            else (
                "A empresa está FECHADA no momento."
                + (f" Retornamos em: {next_open_time}" if next_open_time else "")
            )
        ),
        "schedule_text": schedule_text,
        "current_datetime_readable": current_datetime_readable,
    }
    company_context = ""
    try:
        profile_company = TenantCompanyProfile.objects.filter(tenant_id=tenant_id).first()
        if profile_company:
            company_context = _build_company_chunk(profile_company) or ""
    except Exception:
        pass
    query_embedding = embed_text(message_text) if message_text else []
    knowledge_items = get_secretary_rag_context(
        tenant_id,
        query_embedding,
        limit=getattr(settings, "AI_RAG_TOP_K", 5),
    )
    departments = []
    try:
        from apps.authn.models import Department
        for dept in Department.objects.filter(tenant=tenant).order_by("name"):
            departments.append({
                "id": str(dept.id),
                "name": getattr(dept, "name", "") or "",
                "routing_keywords": getattr(dept, "routing_keywords", []) or [],
            })
    except Exception:
        pass
    now_iso = timezone.now().isoformat()
    _msg_list = list(messages_list) if messages_list else []
    context_messages = []
    for i, m in enumerate(_msg_list):
        role = (m.get("role") or "user").strip().lower()
        content = str(m.get("content") or "")
        if role == "user":
            direction, sender_name = "incoming", "Cliente"
        elif role == "system":
            direction, sender_name = "outgoing", "Sistema"
        else:
            direction, sender_name = "outgoing", "Bia"
        context_messages.append({
            "id": str(uuid.uuid4()) if i < len(_msg_list) - 1 else message_id,
            "direction": direction,
            "content": content,
            "created_at": now_iso,
            "sender_name": sender_name,
        })
    server_time_utc = _server_time_utc_iso()
    tenant_name = getattr(tenant, "name", "") or ""
    prompt_with_data = _build_system_data_block(
        tenant_name, business_hours_info, server_time_utc
    ) + (prompt or "").strip()
    prompt_with_data = _apply_prompt_name_variable(prompt_with_data, signature_name)
    payload = {
        "protocol_version": "v1",
        "action": "secretary",
        "agent_type": "secretary",
        "request_id": request_id,
        "trace_id": trace_id,
        "server_time_utc": server_time_utc,
        "tenant_id": tenant_id,
        "tenant": {"id": tenant_id, "name": tenant_name},
        "business_hours": business_hours_info,
        "company_context": company_context,
        "conversation": {
            "id": conversation_id,
            "status": "open",
            "contact_name": "Teste",
            "contact_phone": "",
            "contact_phone_normalized": "",
            "department": None,
            "department_id": None,
        },
        "message": {
            "id": message_id,
            "direction": "incoming",
            "content": message_text,
            "created_at": now_iso,
        },
        "messages": context_messages,
        "knowledge_items": knowledge_items,
        "memory_items": [],
        "departments": departments,
        "model": model,
        "metadata": {"model": model, "source": "test"},
        "prompt": prompt_with_data,
    }
    return payload


def _send_typing_indicator(conversation, typing_seconds: float = SECRETARY_TYPING_DELAY_SECONDS) -> None:
    """
    Envia indicador "digitando" para a Evolution API antes da secretária responder.
    
    Args:
        conversation: Objeto Conversation
        typing_seconds: Tempo em segundos que o indicador ficará ativo
    """
    try:
        from django.db.models import Q
        from apps.notifications.models import WhatsAppInstance
        from apps.connections.models import EvolutionConnection
        
        # ✅ MULTI-INSTÂNCIA: Priorizar instância da conversa (que recebeu a mensagem)
        instance = None
        if conversation.instance_name and str(conversation.instance_name).strip():
            instance = WhatsAppInstance.objects.filter(
                Q(instance_name=conversation.instance_name.strip())
                | Q(evolution_instance_name=conversation.instance_name.strip()),
                tenant=conversation.tenant,
                is_active=True,
                status='active'
            ).first()
        if not instance:
            instance = WhatsAppInstance.objects.filter(
                tenant=conversation.tenant,
                is_active=True,
                status='active'
            ).first()
        
        if not instance:
            logger.debug("[SECRETARY TYPING] Nenhuma instância WhatsApp ativa para enviar typing indicator")
            return
        
        # Buscar servidor Evolution (fallback)
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        
        # Preparar URL e credenciais
        api_url = instance.api_url or (evolution_server.base_url if evolution_server else None)
        api_key = instance.api_key or (evolution_server.api_key if evolution_server else None)
        
        if not api_url or not api_key:
            logger.debug("[SECRETARY TYPING] API URL ou API key não disponível")
            return
        
        # Preparar dados
        contact_phone = conversation.contact_phone
        if not contact_phone:
            logger.debug("[SECRETARY TYPING] Contact phone não disponível")
            return
        
        presence_url = f"{api_url.rstrip('/')}/chat/sendPresence/{instance.instance_name}"
        presence_data = {
            "number": contact_phone,
            "delay": int(typing_seconds * 1000),  # Converter para milissegundos
            "presence": "composing"
        }
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        logger.info(
            "[SECRETARY TYPING] Enviando indicador 'digitando' para %s (delay=%sms)",
            contact_phone,
            presence_data["delay"]
        )
        
        # Enviar request (síncrono, pois estamos em thread)
        response = requests.post(presence_url, json=presence_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info("[SECRETARY TYPING] Indicador 'digitando' enviado com sucesso")
        else:
            logger.warning(
                "[SECRETARY TYPING] Erro %s ao enviar typing indicator: %s",
                response.status_code,
                response.text[:200] if hasattr(response, 'text') else 'N/A'
            )
    except Exception as e:
        # Não bloquear o processamento se o typing indicator falhar
        logger.warning("[SECRETARY TYPING] Erro ao enviar typing indicator: %s", e, exc_info=True)


def _secretary_worker(conversation, message) -> None:
    """Worker em background: chama n8n com contexto da secretária, cria mensagem de resposta, opcionalmente atribui departamento."""
    from django.db import close_old_connections
    from apps.chat.models import Message as ChatMessage
    from apps.chat.utils.serialization import serialize_message_for_ws, serialize_conversation_for_ws
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    close_old_connections()
    start_time = time.time()
    tenant = conversation.tenant
    tenant_id = str(tenant.id)
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=tenant).first()
        profile = TenantSecretaryProfile.objects.filter(tenant=tenant).first()
        if not settings_obj or not getattr(settings_obj, "secretary_enabled", False):
            return
        if not profile or not profile.is_active:
            return
        n8n_url = _resolve_n8n_ai_url(tenant)
        if not n8n_url:
            logger.info("Secretary: n8n AI webhook not configured for tenant %s", tenant_id)
            return

        # Só enviar ao agente quando houver conteúdo: texto ou transcrição de áudio pronta
        content = (getattr(message, "content", None) or "").strip()
        if not content:
            from apps.chat.models import MessageAttachment
            audio_attachments = list(
                message.attachments.filter(mime_type__icontains="audio").only("id", "transcription")
            )
            if audio_attachments:
                has_transcription = any(
                    (getattr(a, "transcription", None) or "").strip()
                    for a in audio_attachments
                )
                if not has_transcription:
                    logger.info(
                        "[SECRETARY] Mensagem é áudio sem transcrição; não enviar ao agente (conv=%s)",
                        conversation.id,
                    )
                    return

        # ✅ NOVO: Enviar indicador "digitando" antes de processar
        _send_typing_indicator(conversation)

        context = _build_secretary_context(conversation, message, profile)
        body = {"action": "secretary", **context}
        logger.info(
            "[SECRETARY] Chamando n8n url=%s conversation_id=%s model=%s",
            n8n_url[:50] + "..." if len(n8n_url) > 50 else n8n_url,
            conversation.id,
            body.get("model"),
        )

        last_error = None
        for attempt in range(2):
            try:
                resp = requests.post(n8n_url, json=body, timeout=SECRETARY_N8N_TIMEOUT)
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    time.sleep(SECRETARY_N8N_RETRY_DELAY)
                else:
                    logger.warning("Secretary n8n call failed for tenant %s: %s", tenant_id, e, exc_info=True)
                    return
        else:
            if last_error:
                raise last_error
            return

        reply_text = (data.get("reply_text") or "").strip()
        # Não criar mensagem se o modelo não respondeu (fallback do n8n)
        if not reply_text or reply_text == "(Sem resposta do modelo.)":
            return

        latency_ms = int((time.time() - start_time) * 1000)
        request_id = data.get("request_id")
        trace_id = data.get("trace_id")
        meta = data.get("meta") or {}
        input_tokens = meta.get("input_tokens") if isinstance(meta.get("input_tokens"), int) else None
        output_tokens = meta.get("output_tokens") if isinstance(meta.get("output_tokens"), int) else None

        sender_name = (getattr(profile, "signature_name", None) or "").strip() or "Assistente"
        message_obj = ChatMessage.objects.create(
            conversation=conversation,
            sender=None,
            sender_name=sender_name,
            content=reply_text,
            direction="outgoing",
            status="pending",
            is_internal=False,
        )
        room_group_name = f"chat_tenant_{tenant_id}_conversation_{conversation.id}"
        tenant_group = f"chat_tenant_{tenant_id}"
        channel_layer = get_channel_layer()
        msg_data = serialize_message_for_ws(message_obj)
        conv_data = serialize_conversation_for_ws(conversation)
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {"type": "message_received", "message": msg_data},
        )
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {"type": "message_received", "message": msg_data, "conversation": conv_data},
        )
        from apps.chat.tasks import send_message_to_evolution
        send_message_to_evolution.delay(str(message_obj.id))

        # ✅ NOVO: Marcar mensagens do cliente como recebidas e lidas quando a secretária responde
        try:
            from apps.chat.webhooks import send_delivery_receipt, send_read_receipt
            unread_messages = ChatMessage.objects.filter(
                conversation=conversation,
                direction='incoming',
                status__in=['sent', 'delivered']  # Mensagens ainda não lidas
            ).order_by('created_at')
            
            for unread_msg in unread_messages:
                if unread_msg.message_id:  # Só marcar se tiver message_id da Evolution
                    # Marcar como entregue (✓✓ cinza)
                    send_delivery_receipt(conversation, unread_msg)
                    # Pequeno delay antes de marcar como lida (simula leitura humana)
                    time.sleep(0.5)
                    # Marcar como lida (✓✓ azul)
                    read_success = send_read_receipt(conversation, unread_msg, max_retries=2)
                    if read_success:
                        # Atualizar status no banco para 'seen'
                        unread_msg.status = 'seen'
                        unread_msg.save(update_fields=['status'])
                        logger.info(
                            "[SECRETARY] Mensagem marcada como recebida e lida: message_id=%s",
                            unread_msg.message_id
                        )
                    else:
                        logger.warning(
                            "[SECRETARY] Falha ao marcar mensagem como lida: message_id=%s",
                            unread_msg.message_id
                        )
        except Exception as e:
            # Não bloquear o processamento se falhar ao marcar como lida
            logger.warning("[SECRETARY] Erro ao marcar mensagens como lidas: %s", e, exc_info=True)

        suggested_department_id = data.get("suggested_department_id")
        summary_for_department = (data.get("summary_for_department") or "").strip()
        # Fallback: quando há transferência mas a IA não enviou resumo, usar mensagem que disparou
        if suggested_department_id and not summary_for_department:
            trigger_content = (_message_content_for_secretary(message) or "").strip()
            # Placeholders de mídia sem texto não servem como resumo; usar mensagem fixa
            uninformative = (
                not trigger_content
                or trigger_content == "[Áudio em processamento]"
                or trigger_content in ("[Imagem]", "[Vídeo]", "[Imagem e vídeo]")
            )
            if uninformative:
                summary_for_department = "Solicitação do cliente (resumo não disponível)."
            else:
                summary_for_department = (trigger_content[:300] + ("…" if len(trigger_content) > 300 else ""))
            logger.info(
                "[SECRETARY] Resumo não veio do N8N; usando fallback (conv=%s, len=%s)",
                conversation.id, len(summary_for_department),
            )
        if suggested_department_id:
            try:
                from apps.authn.models import Department
                dept = Department.objects.filter(
                    tenant=tenant,
                    id=suggested_department_id,
                ).first()
                if dept:
                    conversation.department = dept
                    conversation.status = "open"
                    update_fields = ["department", "status"]
                    if summary_for_department:
                        meta = getattr(conversation, "metadata", None) or {}
                        if not isinstance(meta, dict):
                            meta = {}
                        meta["secretary_summary"] = summary_for_department[:2000]
                        conversation.metadata = meta
                        update_fields.append("metadata")
                    conversation.save(update_fields=update_fields)

                    # Mensagem interna para o departamento (resumo visível no chat)
                    internal_content = f"Conversa transferida para {dept.name} ({sender_name}). Resumo: {summary_for_department[:500] if summary_for_department else '—'}"
                    ChatMessage.objects.create(
                        conversation=conversation,
                        sender=None,
                        sender_name="Sistema",
                        content=internal_content,
                        direction="outgoing",
                        status="sent",
                        is_internal=True,
                    )

                    # Confirmação ao cliente: transfer_message do departamento ou padrão; opcionalmente resumo (limite 200)
                    confirmation_text = (getattr(dept, "transfer_message", None) or "").strip()
                    if not confirmation_text:
                        confirmation_text = f"Sua conversa foi transferida para o departamento {dept.name}. Em breve você será atendido."
                    if summary_for_department:
                        summary_line = (summary_for_department[:200] + ("…" if len(summary_for_department) > 200 else ""))
                        confirmation_text = f"{confirmation_text}\n\nResumo do que você nos disse: {summary_line}"

                    confirmation_message = ChatMessage.objects.create(
                        conversation=conversation,
                        sender=None,
                        sender_name=sender_name,
                        content=confirmation_text,
                        direction="outgoing",
                        status="pending",
                        is_internal=False,
                    )
                    conv_data_after = serialize_conversation_for_ws(conversation)
                    msg_conf_data = serialize_message_for_ws(confirmation_message)
                    async_to_sync(channel_layer.group_send)(
                        room_group_name,
                        {"type": "message_received", "message": msg_conf_data},
                    )
                    async_to_sync(channel_layer.group_send)(
                        tenant_group,
                        {"type": "message_received", "message": msg_conf_data, "conversation": conv_data_after},
                    )
                    send_message_to_evolution.delay(str(confirmation_message.id))
            except Exception as e:
                logger.warning("Secretary: failed to assign department %s: %s", suggested_department_id, e)

        # Registro de retorno (Bia): criar tarefa na agenda quando fora do horário
        if data.get("register_return") and (data.get("return_subject") or "").strip():
            return_subject = (data.get("return_subject") or "").strip()
            return_department_id = (data.get("return_department_id") or "").strip() or None
            try:
                from apps.chat.services.business_hours_service import BusinessHoursService
                BusinessHoursService.create_secretary_return_task(
                    conversation=conversation,
                    message=message,
                    tenant=tenant,
                    return_subject=return_subject,
                    return_department_id=return_department_id,
                )
            except Exception as e:
                logger.warning(
                    "Secretary: create_secretary_return_task failed conv=%s: %s",
                    conversation.id, e, exc_info=True,
                )

        # Encerrar conversa no app quando a Bia se despede (ex.: após registrar retorno)
        if data.get("close_conversation"):
            try:
                conversation.status = "closed"
                conversation.assigned_to = None
                conversation.department = None
                conversation.save(update_fields=["status", "assigned_to", "department"])
                conv_data_closed = serialize_conversation_for_ws(conversation)
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {"type": "message_received", "conversation": conv_data_closed},
                )
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {"type": "message_received", "conversation": conv_data_closed},
                )
                logger.info(
                    "[SECRETARY] Conversa encerrada no app (Bia se despediu): conv=%s",
                    conversation.id,
                )
            except Exception as e:
                logger.warning(
                    "Secretary: close_conversation failed conv=%s: %s",
                    conversation.id, e, exc_info=True,
                )

        memory_items = data.get("memory_items") or []
        if memory_items and profile.use_memory:
            from datetime import timedelta
            retention_days = getattr(settings, "AI_MEMORY_RETENTION_DAYS", 180)
            expires_at = timezone.now() + timedelta(days=retention_days)
            for item in memory_items:
                content = (item or {}).get("content")
                if not content:
                    continue
                emb = embed_text(content)
                AiMemoryItem.objects.create(
                    tenant=tenant,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    kind=(item or {}).get("kind", "fact"),
                    content=content,
                    metadata=(item or {}).get("metadata", {}),
                    embedding=emb or None,
                    expires_at=expires_at,
                )

        try:
            AiGatewayAudit.objects.create(
                tenant=tenant,
                conversation_id=conversation.id,
                message_id=message.id,
                request_id=request_id or __import__("uuid").uuid4(),
                trace_id=trace_id or __import__("uuid").uuid4(),
                status="success",
                latency_ms=latency_ms,
                handoff=bool(suggested_department_id),
                input_summary="",  # Não logar conteúdo completo (segurança)
                output_summary=reply_text[:200] if reply_text else "",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                agent_type="bia",
            )
        except Exception:
            pass
    except Exception as e:
        logger.exception("Secretary worker failed for conversation %s: %s", conversation.id, e)
    finally:
        close_old_connections()


def dispatch_secretary_async(conversation, message) -> None:
    """
    Dispara o worker da Secretária em thread (Inbox + secretary_enabled).
    Chamar apenas quando conversa está no Inbox (department is None) e mensagem é incoming.
    """
    logger.info(
        "[SECRETARY] Avaliando: conv=%s dept_id=%s msg=%s",
        conversation.id, conversation.department_id, message.id,
    )
    if conversation.department_id is not None:
        logger.info(
            "[SECRETARY] Skip: conversa não está no Inbox (department_id=%s)",
            conversation.department_id,
        )
        return
    try:
        settings_obj = TenantAiSettings.objects.filter(tenant=conversation.tenant).first()
        if not settings_obj:
            logger.info("[SECRETARY] Skip: tenant sem ai_settings")
            return
        if not getattr(settings_obj, "secretary_enabled", False):
            logger.info("[SECRETARY] Skip: secretary_enabled desligado para tenant %s", conversation.tenant_id)
            return
        profile = TenantSecretaryProfile.objects.filter(tenant=conversation.tenant).first()
        if not profile:
            logger.info("[SECRETARY] Skip: tenant sem secretary_profile")
            return
        if not profile.is_active:
            logger.info("[SECRETARY] Skip: perfil da secretária inativo (is_active=False) para tenant %s", conversation.tenant_id)
            return
        n8n_url = _resolve_n8n_ai_url(conversation.tenant)
        if not n8n_url:
            logger.info("[SECRETARY] Skip: webhook da IA não configurado (n8n_ai_webhook_url vazio) para tenant %s", conversation.tenant_id)
            return
        # BIA não atende grupos WhatsApp
        if "g.us" in (conversation.contact_phone or ""):
            logger.info("[SECRETARY] Skip: conversa de grupo (BIA não atende grupos)")
            return
    except Exception as e:
        logger.warning("[SECRETARY] Skip: exceção ao checar condições: %s", e, exc_info=True)
        return
    logger.info(
        "[SECRETARY] Disparando worker para conversation_id=%s message_id=%s tenant_id=%s",
        conversation.id,
        message.id,
        conversation.tenant_id,
    )
    thread = threading.Thread(target=_secretary_worker, args=(conversation, message), daemon=True)
    thread.start()
