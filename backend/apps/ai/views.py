import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, time as dt_time
import uuid
import requests

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

# from .tasks import analyze_message_async  # Removido - Celery deletado
from apps.chat.models import Conversation, Message as ChatMessage
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.ai.models import (
    AgentAssignment,
    AiGatewayAudit,
    AiTriageResult,
    TenantAiSettings,
    TenantSecretaryProfile,
    AiTranscriptionDailyMetric,
    ConversationSummary,
    ConsolidationRecord,
    DifySettings,
    DifyAppCatalogItem,
    DifyAssignment,
    DifyAuditLog,
)
from apps.tenancy.models import Tenant
from apps.connections.webhook_cache import get_redis_client
from apps.ai.transcription_metrics import (
    aggregate_transcription_metrics,
    build_transcription_queryset,
    rebuild_transcription_metrics,
    resolve_date_range,
)
from apps.ai.triage_service import run_test_prompt, run_transcription_test
from apps.ai.throttling import GatewayReplyThrottle, GatewayTestThrottle
from apps.ai.secretary_service import (
    build_secretary_payload_for_test,
    DEFAULT_GENERATION_OPTIONS,
    get_effective_generation_options,
    _message_content_for_secretary,
    _server_time_utc_iso,
    validate_and_sanitize_generation_options,
)
from apps.chat.utils.s3 import get_s3_manager, get_public_url

logger = logging.getLogger(__name__)


_MASK_KEYS = {'content', 'reply_text', 'error_message'}


def _mask_text(value: str) -> str:
    if not value:
        return value
    masked = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', value)
    masked = re.sub(r'\b\d{4,}\b', '****', masked)
    return masked


def _mask_payload(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if key in _MASK_KEYS and isinstance(item, str):
                masked[key] = _mask_text(item)
            else:
                masked[key] = _mask_payload(item)
        return masked
    if isinstance(value, list):
        return [_mask_payload(item) for item in value]
    return value


def _safe_summary(value: str, limit: int = 200) -> str:
    if not value:
        return ''
    return _mask_text(value)[:limit]


def _parse_uuid(value):
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _ensure_aware(value):
    if not value:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value)
    return value


def _normalize_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim", "on"}
    return None


# Limite WhatsApp (mensagem de texto)
MAX_REPLY_TEXT_LENGTH = 4096


def _user_can_access_conversation(user, conversation):
    """Verifica se o usuário pode acessar a conversa (mesma lógica de CanAccessChat)."""
    if user.is_admin:
        return True
    department = getattr(conversation, 'department', None)
    if department:
        return user.departments.filter(id=department.id).exists()
    return user.is_gerente or user.is_agente


def _create_and_broadcast_message(conversation, sender, content, is_internal=False):
    """
    Cria mensagem no chat, faz broadcast via WebSocket e enfileira envio para Evolution API.
    Retorna a mensagem criada.
    """
    message = ChatMessage.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
        direction='outgoing',
        status='pending',
        is_internal=is_internal,
    )
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.chat.utils.serialization import serialize_message_for_ws, serialize_conversation_for_ws

        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        tenant_group = f"chat_tenant_{conversation.tenant_id}"

        msg_data_serializable = serialize_message_for_ws(message)
        conv_data_serializable = serialize_conversation_for_ws(conversation)

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {'type': 'message_received', 'message': msg_data_serializable}
        )
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {
                'type': 'message_received',
                'message': msg_data_serializable,
                'conversation': conv_data_serializable
            }
        )

        from apps.chat.tasks import send_message_to_evolution
        send_message_to_evolution.delay(str(message.id))

        logger.info(
            "✅ [GATEWAY] Mensagem criada e enviada: conversation=%s, message=%s",
            conversation.id, message.id
        )
    except Exception as e:
        logger.error("❌ [GATEWAY] Erro ao broadcast/enviar mensagem: %s", e, exc_info=True)
    return message


def _serialize_ai_settings(settings_obj: TenantAiSettings) -> dict:
    return {
        "ai_enabled": settings_obj.ai_enabled,
        "audio_transcription_enabled": settings_obj.audio_transcription_enabled,
        "transcription_auto": settings_obj.transcription_auto,
        "transcription_min_seconds": settings_obj.transcription_min_seconds,
        "transcription_max_mb": settings_obj.transcription_max_mb,
        "triage_enabled": settings_obj.triage_enabled,
        "secretary_enabled": getattr(settings_obj, 'secretary_enabled', False),
        "secretary_model": getattr(settings_obj, 'secretary_model', '') or '',
        "agent_model": settings_obj.agent_model,
        "n8n_audio_webhook_url": settings_obj.n8n_audio_webhook_url or "",
        "n8n_triage_webhook_url": settings_obj.n8n_triage_webhook_url or "",
        "n8n_ai_webhook_url": settings_obj.n8n_ai_webhook_url or "",
        "n8n_models_webhook_url": settings_obj.n8n_models_webhook_url or "",
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def analyze_message(request, message_id):
    """Force analysis of a specific message."""
    
    try:
        message = Message.objects.get(
            id=message_id,
            tenant=request.user.tenant
        )
    except Message.DoesNotExist:
        return Response(
            {'error': 'Message not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Queue analysis task
    # analyze_message_async.delay(  # Removido - Celery deletado
    #     tenant_id=str(request.user.tenant.id),
    #     message_id=message.id,
    #     is_shadow=False,
    #     run_id="manual"
    # )
    # TODO: Implementar com RabbitMQ
    
    return Response({
        'status': 'success',
        'message': 'Analysis queued',
        'message_id': message.id
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def analyze_batch(request):
    """Analyze multiple messages."""
    
    message_ids = request.data.get('message_ids', [])
    if not message_ids:
        return Response(
            {'error': 'No message IDs provided'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify all messages belong to tenant
    messages = Message.objects.filter(
        id__in=message_ids,
        tenant=request.user.tenant
    )
    
    if len(messages) != len(message_ids):
        return Response(
            {'error': 'Some messages not found or access denied'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Queue analysis tasks
    queued_count = 0
    for message in messages:
        # analyze_message_async.delay(  # Removido - Celery deletado
        #     tenant_id=str(request.user.tenant.id),
        #     message_id=message.id,
        #     is_shadow=False,
        #     run_id="batch"
        # )
        # TODO: Implementar com RabbitMQ
        queued_count += 1
    
    return Response({
        'status': 'success',
        'message': f'Queued {queued_count} messages for analysis',
        'queued_count': queued_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def ai_stats(request):
    """Get AI analysis statistics."""
    
    from apps.experiments.models import Inference
    from django.db.models import Avg, Count
    
    tenant = request.user.tenant
    
    # Get inference stats
    inferences = Inference.objects.filter(tenant=tenant)
    
    stats = {
        'total_inferences': inferences.count(),
        'avg_latency_ms': inferences.aggregate(avg=Avg('latency_ms'))['avg'] or 0,
        'models_used': list(inferences.values_list('model_name', flat=True).distinct()),
        'prompt_versions': list(inferences.values_list('prompt_version', flat=True).distinct()),
        'shadow_inferences': inferences.filter(is_shadow=True).count(),
        'champion_inferences': inferences.filter(is_shadow=False).count(),
    }
    
    # Recent performance
    recent_inferences = inferences.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    )
    
    stats['recent_avg_latency_ms'] = recent_inferences.aggregate(
        avg=Avg('latency_ms')
    )['avg'] or 0
    
    stats['recent_inference_count'] = recent_inferences.count()
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def triage_test(request):
    """Run a triage test prompt via N8N."""
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=request.user.tenant)
    triage_webhook = settings_obj.n8n_triage_webhook_url or getattr(settings, 'N8N_TRIAGE_WEBHOOK', '')
    if settings_obj.triage_enabled and not triage_webhook:
        return Response(
            {"error": "Webhook de triagem obrigatório quando habilitado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payload = {
        "message": request.data.get("message", ""),
        "prompt": request.data.get("prompt", ""),
        "context": request.data.get("context", {}),
    }

    try:
        response_data = run_test_prompt(request.user.tenant, payload)
        return Response({"status": "success", "data": response_data})
    except Exception as exc:
        return Response(
            {"status": "error", "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )


MAX_PROMPT_LENGTH = 1_000_000  # ~1 MB em texto típico (UTF-8)
MAX_KNOWLEDGE_ITEMS = 5
MAX_KNOWLEDGE_CONTENT_LENGTH = 50000
MAX_CHAT_MESSAGES = 50
GATEWAY_TEST_WEBHOOK_TIMEOUT = 60

# Gateway test async: Redis key prefix and TTL
GATEWAY_TEST_RESULT_KEY_PREFIX = "gateway_test_result:"


def _gateway_test_result_ttl():
    return getattr(settings, 'GATEWAY_TEST_RESULT_TTL_SECONDS', 600)


def _gateway_test_set_pending(job_id, tenant_id, request_id, trace_id):
    """Grava job pending no Redis. Retorna True se ok, False se Redis indisponível."""
    client = get_redis_client()
    if not client:
        return False
    key = f"{GATEWAY_TEST_RESULT_KEY_PREFIX}{job_id}"
    value = {
        "tenant_id": str(tenant_id),
        "status": "pending",
        "request_id": str(request_id),
        "trace_id": str(trace_id),
        "created_at": timezone.now().isoformat(),
    }
    try:
        client.setex(key, _gateway_test_result_ttl(), json.dumps(value))
        return True
    except Exception as e:
        logger.warning("gateway_test Redis set pending failed: %s", e)
        return False


def _gateway_test_get_result(job_id):
    """Retorna dict do job (tenant_id, status, response, error) ou None se não existir."""
    client = get_redis_client()
    if not client:
        return None
    key = f"{GATEWAY_TEST_RESULT_KEY_PREFIX}{job_id}"
    try:
        raw = client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("gateway_test Redis get failed: %s", e)
        return None


def _gateway_test_set_result(job_id, status, response=None, error_message=None, request_id=None, trace_id=None):
    """Atualiza job no Redis (completed/failed). Só deve ser chamado se a chave já existir."""
    client = get_redis_client()
    if not client:
        return False
    key = f"{GATEWAY_TEST_RESULT_KEY_PREFIX}{job_id}"
    try:
        existing = client.get(key)
        if not existing:
            return False
        data = json.loads(existing)
        data["status"] = status
        if response is not None:
            data["response"] = response
        if error_message is not None:
            data["error"] = error_message
        if request_id is not None:
            data["request_id"] = str(request_id)
        if trace_id is not None:
            data["trace_id"] = str(trace_id)
        client.setex(key, _gateway_test_result_ttl(), json.dumps(data))
        return True
    except Exception as e:
        logger.warning("gateway_test Redis set result failed: %s", e)
        return False


def _gateway_test_delete_result(job_id):
    """Remove job do Redis (ex.: quando n8n responde síncrono)."""
    client = get_redis_client()
    if not client:
        return
    key = f"{GATEWAY_TEST_RESULT_KEY_PREFIX}{job_id}"
    try:
        client.delete(key)
    except Exception as e:
        logger.warning("gateway_test Redis delete failed: %s", e)


@api_view(['POST'])
@permission_classes([AllowAny])
def gateway_test_callback(request):
    """
    Callback chamado pelo n8n ao terminar o processamento assíncrono do gateway de teste.
    Autenticação: header X-Gateway-Callback-Token. Só atualiza chave existente no Redis.
    """
    token = (request.headers.get('X-Gateway-Callback-Token') or '').strip()
    expected = (getattr(settings, 'GATEWAY_TEST_CALLBACK_TOKEN', None) or '').strip()
    if not expected or token != expected:
        return Response({'detail': 'Invalid token.'}, status=status.HTTP_403_FORBIDDEN)

    job_id_raw = request.data.get('job_id')
    job_id = _parse_uuid(job_id_raw)
    if not job_id:
        return Response({'detail': 'job_id (UUID) required.'}, status=status.HTTP_400_BAD_REQUEST)

    callback_status = request.data.get('status')
    if callback_status not in ('success', 'error'):
        return Response({'detail': 'status must be success or error.'}, status=status.HTTP_400_BAD_REQUEST)

    response_payload = request.data.get('response')
    error_message = (request.data.get('error_message') or '').strip()
    request_id = _parse_uuid(request.data.get('request_id'))
    trace_id = _parse_uuid(request.data.get('trace_id'))

    # Só atualizar se a chave já existir (não criar resultado para job_id desconhecido)
    internal_status = 'completed' if callback_status == 'success' else 'failed'
    updated = _gateway_test_set_result(
        job_id,
        status=internal_status,
        response=response_payload if callback_status == 'success' else None,
        error_message=error_message if callback_status == 'error' else None,
        request_id=request_id,
        trace_id=trace_id,
    )
    if not updated:
        logger.info("gateway_test callback: job inexistente ou expirado")
        return Response({'detail': 'Job not found or expired.'}, status=status.HTTP_200_OK)

    # Auditoria: criar AiGatewayAudit no callback (tenant vem do Redis)
    job_data = _gateway_test_get_result(job_id)
    if job_data:
        tenant_id = job_data.get('tenant_id')
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            pass
        else:
            reply_text = ''
            if internal_status == 'completed' and response_payload:
                reply_text = str(response_payload.get('reply_text') or response_payload.get('text') or '')
            AiGatewayAudit.objects.create(
                tenant=tenant,
                conversation_id=None,
                message_id=uuid.uuid4(),
                contact_id=None,
                department_id=None,
                agent_id=None,
                request_id=request_id or uuid.uuid4(),
                trace_id=trace_id or uuid.uuid4(),
                status='success' if internal_status == 'completed' else 'failed',
                model_name='',
                latency_ms=None,
                rag_hits=None,
                prompt_version='',
                input_summary=_safe_summary(''),
                output_summary=_safe_summary(reply_text),
                handoff=False,
                handoff_reason='',
                error_code='' if internal_status == 'completed' else 'CALLBACK_ERROR',
                error_message=error_message,
                request_payload_masked={},
                response_payload_masked=_mask_payload(response_payload) if response_payload else {},
            )
    return Response({'detail': 'OK'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def gateway_test_result(request, job_id):
    """
    Retorna o resultado de um job de teste do gateway (polling).
    404 se job não existir ou pertencer a outro tenant.
    """
    job_data = _gateway_test_get_result(job_id)
    if not job_data:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    job_tenant_id = job_data.get('tenant_id')
    if not job_tenant_id or str(request.user.tenant_id) != str(job_tenant_id):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    status_value = job_data.get('status', 'pending')
    payload = {'status': status_value}
    if status_value == 'completed':
        payload['response'] = job_data.get('response') or {}
    elif status_value == 'failed':
        payload['error'] = job_data.get('error') or ''
    return Response(payload, status=status.HTTP_200_OK)


# Secretária IA: limites de validação (segurança e desempenho)
SECRETARY_FORM_DATA_MAX_JSON_BYTES = 50_000
SECRETARY_ROUTING_KEYWORDS_MAX_ITEMS = 50
SECRETARY_ROUTING_KEYWORD_MAX_LENGTH = 100


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_bia_admin_key(request):
    """
    Valida a chave de acesso à página admin da BIA.
    Qualquer usuário autenticado pode chamar; retorna 200 { "valid": true } se a chave bater.
    Usado para travar o acesso à página /admin/bia com uma chave única (BIA_ADMIN_ACCESS_KEY).
    """
    key = (request.data.get('key') or request.query_params.get('key') or '').strip()
    expected = (getattr(settings, 'BIA_ADMIN_ACCESS_KEY', None) or '').strip()
    if not expected:
        return Response({'detail': 'Chave não configurada no servidor.'}, status=status.HTTP_403_FORBIDDEN)
    if not key or key != expected:
        return Response({'detail': 'Chave inválida.'}, status=status.HTTP_403_FORBIDDEN)
    return Response({'valid': True})


SUMMARIZE_TIMEOUT = 30


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def test_summarize(request):
    """
    Teste de sumarização: envia mensagens de uma conversa existente ao webhook
    N8N_SUMMARIZE_WEBHOOK_URL e retorna o resumo. Não persiste RAG nem metadata.
    Body: { "conversation_id": "uuid" }.
    """
    conversation_id = _parse_uuid(request.data.get('conversation_id'))
    if not conversation_id:
        return Response(
            {'error': 'conversation_id (UUID) é obrigatório.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    summarize_url = (getattr(settings, 'N8N_SUMMARIZE_WEBHOOK_URL', None) or '').strip()
    if not summarize_url:
        return Response(
            {'error': 'N8N_SUMMARIZE_WEBHOOK_URL não configurado.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    conversation = Conversation.objects.filter(
        id=conversation_id,
        tenant=request.user.tenant,
    ).first()
    if not conversation:
        return Response(
            {'error': 'Conversa não encontrada ou sem permissão.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    if 'g.us' in (conversation.contact_phone or ''):
        return Response(
            {'error': 'Conversas de grupo não são sumarizadas.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    messages_qs = ChatMessage.objects.filter(
        conversation_id=conversation_id,
        is_deleted=False,
    ).order_by('created_at').values('direction', 'content', 'sender_name', 'created_at')
    messages_list = [
        {
            'direction': m['direction'],
            'content': (m['content'] or '')[:10000],
            'sender_name': (m['sender_name'] or '')[:200],
            'created_at': m['created_at'].isoformat() if m['created_at'] else None,
        }
        for m in messages_qs
    ]
    if not messages_list:
        return Response(
            {'error': 'Conversa sem mensagens.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    contact_phone_normalized = normalize_contact_phone_for_rag(conversation.contact_phone or '')
    payload = {
        'tenant_id': str(conversation.tenant_id),
        'conversation_id': str(conversation.id),
        'contact_phone': contact_phone_normalized,
        'contact_name': (conversation.contact_name or '')[:200],
        'messages': messages_list,
    }
    try:
        resp = requests.post(summarize_url, json=payload, timeout=SUMMARIZE_TIMEOUT)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        summary = (data.get('summary') or '').strip()
        return Response({'summary': summary or '(resposta sem campo summary)'})
    except requests.RequestException as e:
        logger.warning('[BIA ADMIN] Erro ao chamar summarize: %s', e)
        return Response(
            {'error': str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
@throttle_classes([GatewayTestThrottle])
def gateway_test(request):
    """Run a Gateway IA test prompt via N8N."""
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=request.user.tenant)
    ai_webhook = settings_obj.n8n_ai_webhook_url or getattr(settings, 'N8N_AI_WEBHOOK', '')
    if settings_obj.ai_enabled and not ai_webhook:
        return Response(
            {"error": "Webhook da IA obrigatório quando habilitado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    selected_model = str(request.data.get("model") or "").strip() or settings_obj.agent_model
    message_text = str(request.data.get("message") or "").strip()

    # Prompt de sistema (opcional)
    custom_prompt = ""
    prompt_raw = request.data.get("prompt")
    if prompt_raw is not None:
        prompt = str(prompt_raw).strip()
        if prompt:
            if len(prompt) > MAX_PROMPT_LENGTH:
                return Response(
                    {"error": f"Prompt excede o limite de {MAX_PROMPT_LENGTH} caracteres."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            custom_prompt = "".join(c for c in prompt if ord(c) >= 32 or c in "\n\r\t")

    # Knowledge items RAG (opcional)
    knowledge_items_raw = request.data.get("knowledge_items")
    knowledge_items_payload = []
    if knowledge_items_raw is not None:
        if not isinstance(knowledge_items_raw, list):
            return Response(
                {"error": "knowledge_items deve ser uma lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(knowledge_items_raw) > MAX_KNOWLEDGE_ITEMS:
            return Response(
                {"error": f"Máximo de {MAX_KNOWLEDGE_ITEMS} itens de conhecimento permitido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for i, item in enumerate(knowledge_items_raw):
            if not isinstance(item, dict):
                return Response(
                    {"error": f"knowledge_items[{i}] deve ser um objeto com title e content."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            title = str(item.get("title") or "").strip() or f"Documento {i + 1}"
            content = str(item.get("content") or "")
            if len(content) > MAX_KNOWLEDGE_CONTENT_LENGTH:
                return Response(
                    {"error": f"Conteúdo do item {i + 1} excede {MAX_KNOWLEDGE_CONTENT_LENGTH} caracteres."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            knowledge_items_payload.append({
                "title": title,
                "content": content,
                "source": "test_upload",
            })

    messages_payload = []
    messages_raw = request.data.get("messages")
    if messages_raw is not None:
        if not isinstance(messages_raw, list):
            return Response(
                {"error": "messages deve ser uma lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(messages_raw) > MAX_CHAT_MESSAGES:
            return Response(
                {"error": f"Máximo de {MAX_CHAT_MESSAGES} mensagens no histórico."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for i, item in enumerate(messages_raw):
            if not isinstance(item, dict):
                return Response(
                    {"error": f"messages[{i}] deve ser um objeto com role e content."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            role = str(item.get("role") or "user").strip().lower()
            if role not in ("user", "assistant", "system"):
                role = "user"
            content = str(item.get("content") or "")
            messages_payload.append({"role": role, "content": content})

    request_id = uuid.uuid4()
    trace_id = uuid.uuid4()

    conversation_id_raw = request.data.get("conversation_id")
    if conversation_id_raw is not None and str(conversation_id_raw).strip():
        conversation_id = _parse_uuid(conversation_id_raw)
        if not conversation_id:
            return Response(
                {"error": "conversation_id inválido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        conversation_id = uuid.uuid4()

    message_id = _parse_uuid(request.data.get("message_id")) or uuid.uuid4()
    contact_id = _parse_uuid(request.data.get("contact_id")) or uuid.uuid4()
    agent_id = _parse_uuid(request.data.get("agent_id")) or _parse_uuid(request.user.id)
    department_id = _parse_uuid(request.data.get("department_id"))
    if not department_id:
        first_department = request.user.departments.first()
        if first_department:
            department_id = first_department.id

    # simulate_production: quando True, envia o mesmo formato da produção (action=secretary, business_hours,
    # departments, RAG, company_context). Usado nas abas Configuração e Homologação da BIA para que o JSON
    # enviado ao webhook seja idêntico ao fluxo real. Quando False, envia payload simples (action=chat).
    simulate_production = request.data.get("simulate_production") is True
    if simulate_production:
        logger.info(
            "[GATEWAY TEST] simulate_production=true: enviando payload secretary (RAG, business_hours, company_context)"
        )
        secretary_profile = TenantSecretaryProfile.objects.filter(tenant=request.user.tenant).first()
        signature_name = getattr(secretary_profile, "signature_name", None) if secretary_profile else None
        payload = build_secretary_payload_for_test(
            tenant=request.user.tenant,
            message_text=message_text,
            messages_list=messages_payload,
            prompt=custom_prompt or "",
            model=selected_model,
            conversation_id=str(conversation_id),
            message_id=str(message_id),
            request_id=str(request_id),
            trace_id=str(trace_id),
            signature_name=signature_name,
        )
    else:
        payload = {
            "protocol_version": "v1",
            "action": "chat",
            "request_id": str(request_id),
            "trace_id": str(trace_id),
            "server_time_utc": _server_time_utc_iso(),
            "tenant_id": str(request.user.tenant_id),
            "conversation_id": str(conversation_id),
            "contact_id": str(contact_id),
            "department_id": str(department_id) if department_id else None,
            "agent_id": str(agent_id) if agent_id else None,
            "message": {
                "id": str(message_id),
                "direction": request.data.get("direction", "incoming"),
                "content": message_text,
                "created_at": timezone.now().isoformat(),
            },
            "metadata": {
                "source": "test",
                "model": selected_model,
            },
        }
        if custom_prompt:
            payload["prompt"] = custom_prompt
        if knowledge_items_payload:
            payload["knowledge_items"] = knowledge_items_payload
        if messages_payload:
            payload["messages"] = messages_payload

    use_async = getattr(settings, 'GATEWAY_TEST_USE_ASYNC', False)
    job_id = None
    webhook_timeout = GATEWAY_TEST_WEBHOOK_TIMEOUT
    if use_async:
        job_id = uuid.uuid4()
        callback_base = (getattr(settings, 'GATEWAY_TEST_CALLBACK_BASE_URL', None) or '').strip().rstrip('/')
        callback_url = f"{callback_base}/api/ai/gateway/test/callback/" if callback_base else ''
        if not _gateway_test_set_pending(job_id, request.user.tenant_id, request_id, trace_id):
            return Response(
                {"error": "Serviço temporariamente indisponível (armazenamento)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        payload["job_id"] = str(job_id)
        payload["callback_url"] = callback_url
        webhook_timeout = getattr(settings, 'GATEWAY_TEST_ASYNC_TIMEOUT', 15)

    start_time = time.monotonic()
    status_value = "success"
    error_code = ""
    error_message = ""
    response_payload = {}

    try:
        response = requests.post(ai_webhook, json=payload, timeout=webhook_timeout)
        response.raise_for_status()
        response_payload = response.json() if response.content else {}
        # Resposta imediata deferred do n8n: retornar ao frontend sem criar audit
        if use_async and job_id and isinstance(response_payload, dict):
            if response_payload.get('deferred') and str(response_payload.get('job_id')) == str(job_id):
                return Response({
                    "deferred": True,
                    "job_id": str(job_id),
                    "message": "Deixe-me pensar...",
                }, status=status.HTTP_200_OK)
        # Resposta completa com use_async: remover job do Redis (callback não será chamado)
        if use_async and job_id:
            _gateway_test_delete_result(job_id)
    except requests.Timeout as exc:
        if use_async and job_id:
            return Response({
                "deferred": True,
                "job_id": str(job_id),
                "message": "Deixe-me pensar...",
            }, status=status.HTTP_200_OK)
        status_value = "failed"
        error_code = "TIMEOUT"
        error_message = str(exc)
        response_payload = {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
        }
    except requests.RequestException as exc:
        if use_async and job_id:
            _gateway_test_delete_result(job_id)
        status_value = "failed"
        error_code = "UPSTREAM_ERROR"
        error_message = str(exc)
        response_payload = {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
        }
    except ValueError as exc:
        if use_async and job_id:
            _gateway_test_delete_result(job_id)
        status_value = "failed"
        error_code = "INVALID_RESPONSE"
        error_message = str(exc)
        response_payload = {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
        }

    latency_ms = int((time.monotonic() - start_time) * 1000)
    response_status = response_payload.get("status") if isinstance(response_payload, dict) else None
    if response_status and response_status != "success":
        status_value = "failed"
        error_code = str(response_payload.get("error_code") or "UPSTREAM_ERROR")
        error_message = str(response_payload.get("error_message") or "")

    meta = (response_payload.get("meta") or {}) if isinstance(response_payload, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    _rp = response_payload if isinstance(response_payload, dict) else {}
    model_name = str(meta.get("model") or _rp.get("model") or selected_model)
    rag_hits = meta.get("rag_hits")
    prompt_version = meta.get("prompt_version") or ""
    handoff = bool(response_payload.get("handoff")) if isinstance(response_payload, dict) else False
    handoff_reason = str(response_payload.get("handoff_reason") or "") if isinstance(response_payload, dict) else ""
    reply_text = str(response_payload.get("reply_text") or response_payload.get("text") or "") if isinstance(response_payload, dict) else ""

    masked_request = _mask_payload(payload)
    masked_response = _mask_payload(response_payload)

    raw_latency = meta.get("latency_ms") if isinstance(meta, dict) else None
    try:
        if raw_latency is not None:
            val = int(float(raw_latency))
            latency_ms_save = max(0, min(val, 2147483647))
        else:
            latency_ms_save = latency_ms
    except (TypeError, ValueError):
        latency_ms_save = latency_ms

    raw_rag_hits = rag_hits
    try:
        if raw_rag_hits is not None:
            val = int(float(raw_rag_hits))
            rag_hits_save = max(0, min(val, 2147483647))
        else:
            rag_hits_save = None
    except (TypeError, ValueError):
        rag_hits_save = None

    AiGatewayAudit.objects.create(
        tenant=request.user.tenant,
        conversation_id=conversation_id,
        message_id=message_id,
        contact_id=contact_id,
        department_id=department_id,
        agent_id=agent_id,
        request_id=request_id,
        trace_id=trace_id,
        status=status_value,
        model_name=model_name or "",
        latency_ms=latency_ms_save,
        rag_hits=rag_hits_save,
        prompt_version=prompt_version or "",
        input_summary=_safe_summary(message_text),
        output_summary=_safe_summary(reply_text),
        handoff=handoff,
        handoff_reason=handoff_reason,
        error_code=error_code,
        error_message=error_message,
        request_payload_masked=masked_request,
        response_payload_masked=masked_response,
    )

    if status_value != "success":
        return Response(
            {
                "status": "error",
                "request_id": str(request_id),
                "trace_id": str(trace_id),
                "error_code": error_code,
                "error_message": error_message or "Falha ao chamar o Gateway IA.",
                "request": masked_request,
                "response": masked_response,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Se conversation_id for real e send_to_chat estiver habilitado, criar mensagem no chat
    send_to_chat_result = None
    send_to_chat = _normalize_bool(request.data.get("send_to_chat")) or False
    if send_to_chat and conversation_id and reply_text:
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                tenant_id=request.user.tenant_id
            )
            if not _user_can_access_conversation(request.user, conversation):
                send_to_chat_result = {"success": False, "error": "SEM_PERMISSÃO_CONVERSA"}
            else:
                _create_and_broadcast_message(conversation, request.user, reply_text, is_internal=False)
                send_to_chat_result = {"success": True}
        except Conversation.DoesNotExist:
            logger.warning("⚠️ [GATEWAY TEST] Conversa não encontrada: %s", conversation_id)
            send_to_chat_result = {"success": False, "error": "CONVERSATION_NOT_FOUND"}
        except Exception as e:
            logger.error("❌ [GATEWAY TEST] Erro ao criar mensagem no chat: %s", e, exc_info=True)
            send_to_chat_result = {"success": False, "error": "INTERNAL_ERROR", "detail": str(e)}
    elif send_to_chat and (not conversation_id or not reply_text):
        send_to_chat_result = {"success": False, "error": "REPLY_VAZIO_OU_CONVERSA_NAO_SELECIONADA"}

    response_body = {
        "status": "success",
        "request_id": str(request_id),
        "trace_id": str(trace_id),
        "data": {
            "request": masked_request,
            "response": masked_response,
        },
    }
    if send_to_chat_result is not None:
        response_body["send_to_chat_result"] = send_to_chat_result

    return Response(response_body)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
@throttle_classes([GatewayReplyThrottle])
def gateway_reply(request):
    """
    Endpoint para n8n enviar respostas da IA diretamente ao chat.
    
    Body esperado:
    {
        "conversation_id": "uuid",
        "request_id": "uuid",  # opcional, para rastreamento
        "trace_id": "uuid",    # opcional, para rastreamento
        "reply_text": "texto da resposta",
        "metadata": {           # opcional
            "model": "...",
            "latency_ms": 123,
            "rag_hits": 5,
            ...
        }
    }
    """
    conversation_id = _parse_uuid(request.data.get("conversation_id"))
    if not conversation_id:
        return Response(
            {"error": "conversation_id é obrigatório"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reply_text = str(request.data.get("reply_text") or "").strip()
    if not reply_text:
        return Response(
            {"error": "reply_text é obrigatório"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(reply_text) > MAX_REPLY_TEXT_LENGTH:
        return Response(
            {"error": f"reply_text excede o limite de {MAX_REPLY_TEXT_LENGTH} caracteres"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        conversation = Conversation.objects.select_related('department').get(
            id=conversation_id,
            tenant_id=request.user.tenant_id
        )
    except Conversation.DoesNotExist:
        return Response(
            {"error": "Conversa não encontrada ou não pertence ao seu tenant"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _user_can_access_conversation(request.user, conversation):
        return Response(
            {"error": "Você não tem permissão para enviar mensagens nesta conversa"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        message = _create_and_broadcast_message(
            conversation, request.user, reply_text, is_internal=False
        )
    except Exception as e:
        logger.error("❌ [GATEWAY REPLY] Erro ao criar mensagem: %s", e, exc_info=True)
        return Response(
            {"error": f"Erro ao criar mensagem: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    request_id = _parse_uuid(request.data.get("request_id"))
    trace_id = _parse_uuid(request.data.get("trace_id"))
    metadata = request.data.get("metadata") or {}
    agent_type = str(request.data.get("agent_type") or "").strip()
    suggested_department_id = request.data.get("suggested_department_id")
    summary_for_department = str(request.data.get("summary_for_department") or "").strip()[:2000]

    # Fallback (callback assíncrono): quando há transferência sem resumo, usar última mensagem incoming
    if suggested_department_id and not summary_for_department:
        last_incoming = (
            conversation.messages.filter(direction="incoming")
            .prefetch_related("attachments")
            .order_by("-created_at")
            .first()
        )
        if last_incoming:
            trigger_content = (_message_content_for_secretary(last_incoming) or "").strip()
            uninformative = (
                not trigger_content
                or trigger_content == "[Áudio em processamento]"
                or trigger_content in ("[Imagem]", "[Vídeo]", "[Imagem e vídeo]")
            )
            if uninformative:
                summary_for_department = "Solicitação do cliente (resumo não disponível)."
            else:
                summary_for_department = (trigger_content[:300] + ("…" if len(trigger_content) > 300 else ""))[:2000]

    if suggested_department_id:
        try:
            from apps.authn.models import Department
            dept = Department.objects.filter(
                tenant_id=request.user.tenant_id,
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
                    meta["secretary_summary"] = summary_for_department
                    conversation.metadata = meta
                    update_fields.append("metadata")
                conversation.save(update_fields=update_fields)
        except Exception as e:
            logger.warning("gateway_reply: failed to assign department %s: %s", suggested_department_id, e)

    if request_id or trace_id or agent_type:
        try:
            AiGatewayAudit.objects.create(
                tenant=request.user.tenant,
                conversation_id=conversation_id,
                message_id=message.id,
                request_id=request_id or uuid.uuid4(),
                trace_id=trace_id or uuid.uuid4(),
                status="success",
                model_name=str(metadata.get("model") or ""),
                latency_ms=metadata.get("latency_ms"),
                rag_hits=metadata.get("rag_hits"),
                output_summary=_safe_summary(reply_text),
                handoff=bool(suggested_department_id),
            )
        except Exception as e:
            logger.warning("⚠️ [GATEWAY REPLY] Erro ao registrar audit: %s", e, exc_info=True)

    return Response(
        {
            "status": "success",
            "message_id": str(message.id),
            "conversation_id": str(conversation_id),
        },
        status=status.HTTP_201_CREATED,
    )


def _validate_secretary_form_data(data) -> tuple:
    """
    Valida e sanitiza form_data da Secretária IA.
    Retorna (dict_sanitizado, None) ou (None, mensagem_erro).
    Regras: apenas dict com valores string/number/list de strings; tamanho máximo; sem scripts.
    """
    if not isinstance(data, dict):
        return None, "form_data deve ser um objeto."
    import json
    # Sanitizar: apenas chaves alfanuméricas e valores primitivos ou lista de strings
    sanitized = {}
    for key, value in data.items():
        if not isinstance(key, str) or not key.replace("_", "").replace("-", "").isalnum():
            continue
        if isinstance(value, str):
            # Remover possíveis scripts
            if "<script" in value.lower() or "javascript:" in value.lower():
                continue
            sanitized[key] = value.strip()[:5000]
        elif isinstance(value, (int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [str(x).strip()[:500] for x in value if isinstance(x, (str, int, float))][:100]
        else:
            continue
    try:
        json_str = json.dumps(sanitized, ensure_ascii=False)
    except (TypeError, ValueError):
        return None, "form_data contém valores não serializáveis."
    if len(json_str.encode("utf-8")) > SECRETARY_FORM_DATA_MAX_JSON_BYTES:
        return None, f"form_data excede o limite de {SECRETARY_FORM_DATA_MAX_JSON_BYTES} bytes."
    return sanitized, None


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def secretary_profile(request):
    """
    GET: retorna o perfil da Secretária IA do tenant (form_data, use_memory, is_active).
    PUT: atualiza perfil; valida form_data e routing_keywords; ao ativar (is_active=True)
         pode disparar atualização do RAG (source=secretary) em background.
    """
    tenant = request.user.tenant
    if request.method == 'GET':
        profile, _ = TenantSecretaryProfile.objects.get_or_create(tenant=tenant)
        logger.info(
            "[SECRETARY PROFILE GET] Retornando perfil: tenant=%s, form_data_keys=%s, form_data_size=%s, is_active=%s",
            tenant.id,
            list(profile.form_data.keys()) if isinstance(profile.form_data, dict) else 'N/A',
            len(str(profile.form_data)) if profile.form_data else 0,
            profile.is_active
        )
        return Response({
            "form_data": profile.form_data,
            "prompt": getattr(profile, 'prompt', '') or '',
            "signature_name": getattr(profile, 'signature_name', '') or '',
            "use_memory": profile.use_memory,
            "is_active": profile.is_active,
            "inbox_idle_minutes": getattr(profile, 'inbox_idle_minutes', 0) or 0,
            "response_delay_seconds": getattr(profile, 'response_delay_seconds', 0) or 0,
            "advanced_options": get_effective_generation_options(profile),
            "created_at": timezone.localtime(profile.created_at).isoformat(),
            "updated_at": timezone.localtime(profile.updated_at).isoformat(),
        })
    # PUT
    data = request.data or {}
    profile, _ = TenantSecretaryProfile.objects.get_or_create(tenant=tenant)
    errors = {}

    if 'form_data' in data:
        fd = data.get('form_data')
        # Evitar logar conteúdo completo (pode conter PII); manter apenas chaves/tamanho em INFO.
        logger.info(
            "[SECRETARY PROFILE PUT] Recebido form_data: keys=%s, tamanho=%s",
            list(fd.keys()) if isinstance(fd, dict) else 'N/A',
            len(str(fd)) if fd else 0,
        )
        sanitized, err = _validate_secretary_form_data(fd)
        if err:
            errors['form_data'] = err
            logger.warning("[SECRETARY PROFILE PUT] Erro na validação: %s", err)
        else:
            logger.info(
                "[SECRETARY PROFILE PUT] form_data sanitizado: keys=%s, tamanho=%s",
                list(sanitized.keys()) if isinstance(sanitized, dict) else 'N/A',
                len(str(sanitized)) if sanitized else 0,
            )
            # Se precisar inspecionar valores, use DEBUG localmente; em produção isso polui e pode expor PII.
            logger.debug(
                "[SECRETARY PROFILE PUT] Campos específicos: email=%s, business_area=%s",
                sanitized.get('email', 'NÃO ENVIADO') if isinstance(sanitized, dict) else 'N/A',
                sanitized.get('business_area', 'NÃO ENVIADO') if isinstance(sanitized, dict) else 'N/A',
            )
            profile.form_data = sanitized

    if 'prompt' in data:
        profile.prompt = (str(data.get('prompt') or '').strip())[:50000]

    if 'signature_name' in data:
        profile.signature_name = (str(data.get('signature_name') or '').strip())[:100]

    if 'use_memory' in data:
        use_memory = _normalize_bool(data.get('use_memory'))
        if use_memory is None:
            errors['use_memory'] = 'Valor inválido.'
        else:
            profile.use_memory = use_memory

    if 'is_active' in data:
        is_active = _normalize_bool(data.get('is_active'))
        if is_active is None:
            errors['is_active'] = 'Valor inválido.'
        else:
            profile.is_active = is_active

    if 'inbox_idle_minutes' in data:
        try:
            val = int(data.get('inbox_idle_minutes'))
            if val < 0 or val > 1440:
                errors['inbox_idle_minutes'] = 'Valor entre 0 e 1440.'
            else:
                profile.inbox_idle_minutes = val
        except (TypeError, ValueError):
            errors['inbox_idle_minutes'] = 'Valor inválido.'

    if 'response_delay_seconds' in data:
        try:
            val = int(data.get('response_delay_seconds'))
            if val < 0 or val > 120:
                errors['response_delay_seconds'] = 'Valor entre 0 e 120.'
            else:
                profile.response_delay_seconds = val
        except (TypeError, ValueError):
            errors['response_delay_seconds'] = 'Valor inválido.'

    if 'advanced_options' in data:
        sanitized_opts, err = validate_and_sanitize_generation_options(data.get('advanced_options'))
        if err:
            errors['advanced_options'] = err
        else:
            if not sanitized_opts:
                profile.generation_options_override = None
            elif all(
                sanitized_opts.get(k) == DEFAULT_GENERATION_OPTIONS.get(k)
                for k in sanitized_opts
            ):
                profile.generation_options_override = None
            else:
                profile.generation_options_override = sanitized_opts

    if errors:
        return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

    profile.save()
    
    # ✅ LOG: Verificar o que foi salvo no banco
    logger.info(
        "[SECRETARY PROFILE PUT] Perfil salvo no banco: tenant=%s, form_data_keys=%s, form_data_size=%s, is_active=%s",
        tenant.id,
        list(profile.form_data.keys()) if isinstance(profile.form_data, dict) else 'N/A',
        len(str(profile.form_data)) if profile.form_data else 0,
        profile.is_active
    )
    
    # Recarregar do banco para garantir que temos os dados mais recentes
    profile.refresh_from_db()
    logger.info(
        "[SECRETARY PROFILE PUT] Após refresh_from_db: form_data_keys=%s, form_data_size=%s",
        list(profile.form_data.keys()) if isinstance(profile.form_data, dict) else 'N/A',
        len(str(profile.form_data)) if profile.form_data else 0
    )

    # RAG upsert desativado – BIA em reconstrução (Fase 0). Será reativado na Fase 5 via pgvector na infra n8n.

    return Response({
        "form_data": profile.form_data,
        "prompt": getattr(profile, 'prompt', '') or '',
        "signature_name": getattr(profile, 'signature_name', '') or '',
        "use_memory": profile.use_memory,
        "is_active": profile.is_active,
        "inbox_idle_minutes": getattr(profile, 'inbox_idle_minutes', 0) or 0,
        "response_delay_seconds": getattr(profile, 'response_delay_seconds', 0) or 0,
        "advanced_options": get_effective_generation_options(profile),
        "updated_at": timezone.localtime(profile.updated_at).isoformat(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def triage_history(request):
    """List recent triage results for the tenant."""
    tenant = request.user.tenant
    queryset = AiTriageResult.objects.filter(tenant=tenant)

    conversation_id = request.query_params.get("conversation_id")
    if conversation_id:
        queryset = queryset.filter(conversation_id=conversation_id)

    pagination = LimitOffsetPagination()
    pagination.default_limit = 50
    results = pagination.paginate_queryset(queryset, request)

    data = [
        {
            "id": item.id,
            "conversation_id": str(item.conversation_id) if item.conversation_id else None,
            "message_id": str(item.message_id) if item.message_id else None,
            "action": item.action,
            "model_name": item.model_name,
            "prompt_version": item.prompt_version,
            "latency_ms": item.latency_ms,
            "status": item.status,
            "result": item.result,
            "created_at": timezone.localtime(item.created_at).isoformat(),
        }
        for item in results
    ]

    return pagination.get_paginated_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def gateway_audit_history(request):
    """List Gateway IA audit entries for the tenant."""
    tenant = request.user.tenant
    queryset = AiGatewayAudit.objects.filter(tenant=tenant)

    conversation_id = request.query_params.get("conversation_id")
    if conversation_id:
        queryset = queryset.filter(conversation_id=conversation_id)

    message_id = request.query_params.get("message_id")
    if message_id:
        queryset = queryset.filter(message_id=message_id)

    status_param = request.query_params.get("status")
    if status_param:
        queryset = queryset.filter(status=status_param)

    model_name = request.query_params.get("model_name")
    if model_name:
        queryset = queryset.filter(model_name__icontains=model_name)

    request_id = request.query_params.get("request_id")
    if request_id:
        queryset = queryset.filter(request_id=request_id)

    trace_id = request.query_params.get("trace_id")
    if trace_id:
        queryset = queryset.filter(trace_id=trace_id)

    created_from = request.query_params.get("created_from")
    if created_from:
        parsed = parse_datetime(created_from)
        if not parsed:
            parsed_date = parse_date(created_from)
            if parsed_date:
                parsed = datetime.combine(parsed_date, dt_time.min)
        aware_value = _ensure_aware(parsed) if parsed else None
        if aware_value:
            queryset = queryset.filter(created_at__gte=aware_value)

    created_to = request.query_params.get("created_to")
    if created_to:
        parsed = parse_datetime(created_to)
        if not parsed:
            parsed_date = parse_date(created_to)
            if parsed_date:
                parsed = datetime.combine(parsed_date, dt_time.max)
        aware_value = _ensure_aware(parsed) if parsed else None
        if aware_value:
            queryset = queryset.filter(created_at__lte=aware_value)

    pagination = LimitOffsetPagination()
    pagination.default_limit = 50
    results = pagination.paginate_queryset(queryset, request)

    data = [
        {
            "id": item.id,
            "conversation_id": str(item.conversation_id) if item.conversation_id else None,
            "message_id": str(item.message_id) if item.message_id else None,
            "contact_id": str(item.contact_id) if item.contact_id else None,
            "department_id": str(item.department_id) if item.department_id else None,
            "agent_id": str(item.agent_id) if item.agent_id else None,
            "request_id": str(item.request_id),
            "trace_id": str(item.trace_id),
            "status": item.status,
            "model_name": item.model_name,
            "latency_ms": item.latency_ms,
            "rag_hits": item.rag_hits,
            "prompt_version": item.prompt_version,
            "input_summary": item.input_summary,
            "output_summary": item.output_summary,
            "handoff": item.handoff,
            "handoff_reason": item.handoff_reason,
            "error_code": item.error_code,
            "error_message": item.error_message,
            "request_payload_masked": item.request_payload_masked,
            "response_payload_masked": item.response_payload_masked,
            "created_at": timezone.localtime(item.created_at).isoformat(),
        }
        for item in results
    ]

    return pagination.get_paginated_response(data)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsTenantMember])
def ai_settings(request):
    tenant = request.user.tenant
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=tenant)

    if request.method == 'GET':
        return Response(_serialize_ai_settings(settings_obj))
    if not request.user.is_admin and not request.user.is_superuser:
        return Response({"error": "Apenas administradores podem alterar configurações."}, status=status.HTTP_403_FORBIDDEN)

    data = request.data or {}
    errors = {}

    def _update_bool(field_name):
        if field_name in data:
            value = _normalize_bool(data.get(field_name))
            if value is None:
                errors[field_name] = 'Valor inválido.'
            else:
                setattr(settings_obj, field_name, value)

    for field in ['ai_enabled', 'audio_transcription_enabled', 'transcription_auto', 'triage_enabled', 'secretary_enabled']:
        _update_bool(field)

    if 'transcription_min_seconds' in data:
        try:
            value = int(data.get('transcription_min_seconds'))
            if value < 0:
                raise ValueError
            settings_obj.transcription_min_seconds = value
        except (TypeError, ValueError):
            errors['transcription_min_seconds'] = 'Valor inválido.'

    if 'transcription_max_mb' in data:
        try:
            value = int(data.get('transcription_max_mb'))
            if value < 0:
                raise ValueError
            settings_obj.transcription_max_mb = value
        except (TypeError, ValueError):
            errors['transcription_max_mb'] = 'Valor inválido.'

    if 'agent_model' in data:
        settings_obj.agent_model = str(data.get('agent_model') or '').strip()

    if 'secretary_model' in data:
        settings_obj.secretary_model = (str(data.get('secretary_model') or '').strip())[:100]

    if 'n8n_audio_webhook_url' in data:
        url = str(data.get('n8n_audio_webhook_url') or '').strip()
        settings_obj.n8n_audio_webhook_url = url

    if 'n8n_triage_webhook_url' in data:
        url = str(data.get('n8n_triage_webhook_url') or '').strip()
        settings_obj.n8n_triage_webhook_url = url

    if 'n8n_ai_webhook_url' in data:
        url = str(data.get('n8n_ai_webhook_url') or '').strip()
        settings_obj.n8n_ai_webhook_url = url

    if 'n8n_models_webhook_url' in data:
        url = str(data.get('n8n_models_webhook_url') or '').strip()
        settings_obj.n8n_models_webhook_url = url

    audio_webhook = settings_obj.n8n_audio_webhook_url or getattr(settings, 'N8N_AUDIO_WEBHOOK', '')
    triage_webhook = settings_obj.n8n_triage_webhook_url or getattr(settings, 'N8N_TRIAGE_WEBHOOK', '')
    ai_webhook = settings_obj.n8n_ai_webhook_url or getattr(settings, 'N8N_AI_WEBHOOK', '')
    models_webhook = settings_obj.n8n_models_webhook_url or getattr(settings, 'N8N_MODELS_WEBHOOK', '')

    if settings_obj.audio_transcription_enabled and not audio_webhook:
        errors['n8n_audio_webhook_url'] = 'Webhook de transcrição obrigatório quando habilitado.'

    if settings_obj.triage_enabled and not triage_webhook:
        errors['n8n_triage_webhook_url'] = 'Webhook de triagem obrigatório quando habilitado.'

    if settings_obj.ai_enabled and not ai_webhook:
        errors['n8n_ai_webhook_url'] = 'Webhook da IA obrigatório quando IA estiver habilitada.'

    if settings_obj.ai_enabled and not models_webhook:
        errors['n8n_models_webhook_url'] = 'Webhook de modelos obrigatório quando IA estiver habilitada.'

    if errors:
        return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

    settings_obj.save()
    return Response(_serialize_ai_settings(settings_obj))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def transcribe_test(request):
    tenant = request.user.tenant
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=tenant)
    audio_webhook = settings_obj.n8n_audio_webhook_url or getattr(settings, 'N8N_AUDIO_WEBHOOK', '')
    if settings_obj.audio_transcription_enabled and not audio_webhook:
        return Response(
            {"error": "Webhook de transcrição obrigatório quando habilitado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    audio_file = request.FILES.get('file')
    media_url = request.data.get('media_url')
    direction = request.data.get('direction', 'incoming')
    conversation_id = request.data.get('conversation_id')
    message_id = request.data.get('message_id')

    if not audio_file and not media_url:
        return Response(
            {"error": "Envie um arquivo de áudio ou informe media_url."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    size_bytes = None

    if audio_file:
        if not (audio_file.content_type or '').startswith('audio/'):
            return Response(
                {"error": "Arquivo precisa ser de áudio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_bytes = max(settings_obj.transcription_max_mb or 0, 0) * 1024 * 1024
        if max_bytes and audio_file.size > max_bytes:
            return Response(
                {"error": "Arquivo excede o limite configurado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_name = audio_file.name or "audio"
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        s3_path = f"ai/transcriptions/{tenant.id}/tests/{unique_name}"
        file_bytes = audio_file.read()
        size_bytes = len(file_bytes)

        s3_manager = get_s3_manager()
        success, msg = s3_manager.upload_to_s3(
            file_bytes,
            s3_path,
            content_type=audio_file.content_type,
        )
        if not success:
            logger.error("Failed to upload transcription test file: %s", msg)
            return Response(
                {"error": "Falha ao enviar arquivo para storage."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        media_url = get_public_url(s3_path)

    payload = {
        "media_url": media_url,
        "size_bytes": size_bytes,
        "direction": direction,
        "conversation_id": conversation_id,
        "message_id": message_id,
    }

    try:
        response_data = run_transcription_test(tenant, payload)
        return Response({"status": "success", "data": response_data})
    except Exception as exc:
        return Response(
            {"status": "error", "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def webhook_test(request):
    tenant = request.user.tenant
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=tenant)
    webhook_type = str(request.data.get('type') or '').strip().lower()

    if webhook_type not in {'audio', 'triage', 'ai'}:
        return Response(
            {"error": "Tipo de webhook inválido. Use 'audio', 'triage' ou 'ai'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if webhook_type == 'audio':
        webhook_url = settings_obj.n8n_audio_webhook_url or getattr(settings, 'N8N_AUDIO_WEBHOOK', '')
        if settings_obj.audio_transcription_enabled and not webhook_url:
            return Response(
                {"error": "Webhook de transcrição obrigatório quando habilitado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif webhook_type == 'triage':
        webhook_url = settings_obj.n8n_triage_webhook_url or getattr(settings, 'N8N_TRIAGE_WEBHOOK', '')
        if settings_obj.triage_enabled and not webhook_url:
            return Response(
                {"error": "Webhook de triagem obrigatório quando habilitado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        webhook_url = settings_obj.n8n_ai_webhook_url or getattr(settings, 'N8N_AI_WEBHOOK', '')
        if settings_obj.ai_enabled and not webhook_url:
            return Response(
                {"error": "Webhook da IA obrigatório quando habilitado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if not webhook_url:
        return Response(
            {"error": "Webhook não configurado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        response = requests.post(
            webhook_url,
            json={"action": "ping"},
            timeout=5.0,
        )
        response.raise_for_status()
        return Response({"status": "success"})
    except Exception as exc:
        return Response(
            {"status": "error", "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def models_list(request):
    tenant = request.user.tenant
    settings_obj, _ = TenantAiSettings.objects.get_or_create(tenant=tenant)
    override_url = str(request.query_params.get('url') or '').strip()
    models_url = override_url or settings_obj.n8n_models_webhook_url or getattr(settings, 'N8N_MODELS_WEBHOOK', '')

    if not models_url:
        return Response(
            {"error": "Webhook de modelos não configurado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not (models_url.startswith('http://') or models_url.startswith('https://')):
        return Response(
            {"error": "Webhook de modelos inválido."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        response = requests.get(models_url, timeout=5.0)
        if response.status_code == 405:
            response = requests.post(models_url, json={"action": "models"}, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return Response(
            {"error": f"Falha ao buscar modelos: {exc}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_models = []
    if isinstance(data, list):
        raw_models = data
    elif isinstance(data, dict):
        raw_models = data.get('models') or data.get('data') or []

    normalized = []
    for item in raw_models or []:
        value = None
        if isinstance(item, dict):
            value = (
                item.get('value')
                or item.get('name')
                or item.get('model')
                or item.get('id')
                or item.get('label')
            )
        elif isinstance(item, (list, tuple)) and item:
            value = item[0]
        else:
            value = item
        if value:
            normalized.append(str(value))

    return Response({"models": normalized})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def transcription_metrics(request):
    tenant = request.user.tenant
    logger.debug(f"📊 [METRICS] Request from tenant_id={tenant.id} ({tenant.name})")
    created_from = request.query_params.get("created_from")
    created_to = request.query_params.get("created_to")
    department_id = _parse_uuid(request.query_params.get("department_id"))
    agent_id = _parse_uuid(request.query_params.get("agent_id"))

    parsed_from = None
    if created_from:
        parsed_from = parse_datetime(created_from)
        if not parsed_from:
            parsed_date = parse_date(created_from)
            if parsed_date:
                parsed_from = datetime.combine(parsed_date, dt_time.min)
    parsed_to = None
    if created_to:
        parsed_to = parse_datetime(created_to)
        if not parsed_to:
            parsed_date = parse_date(created_to)
            if parsed_date:
                parsed_to = datetime.combine(parsed_date, dt_time.max)

    parsed_from = _ensure_aware(parsed_from) if parsed_from else None
    parsed_to = _ensure_aware(parsed_to) if parsed_to else None

    start_date, end_date = resolve_date_range(parsed_from, parsed_to)
    start_datetime = timezone.make_aware(datetime.combine(start_date, dt_time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, dt_time.max))
    total_days = (end_date - start_date).days + 1

    if department_id or agent_id:
        queryset = build_transcription_queryset(
            tenant,
            created_from=start_datetime,
            created_to=end_datetime,
            department_id=department_id,
            agent_id=agent_id,
        )
        daily, totals = aggregate_transcription_metrics(queryset, start_date, end_date)
        daily_series = [
            {
                "date": entry["date"].isoformat(),
                "minutes_total": entry["minutes_total"],
                "audio_count": entry["audio_count"],
                "success_count": entry["success_count"],
                "failed_count": entry["failed_count"],
                "quality_correct_count": entry["quality_correct_count"],
                "quality_incorrect_count": entry["quality_incorrect_count"],
                "quality_unrated_count": entry["quality_unrated_count"],
                "avg_latency_ms": entry["avg_latency_ms"],
                "models_used": entry["models_used"],
            }
            for entry in daily
        ]
    else:
        rebuild_transcription_metrics(tenant, start_date, end_date)
        # ✅ CRÍTICO: Filtrar por tenant para garantir isolamento
        metrics = AiTranscriptionDailyMetric.objects.filter(
            tenant_id=tenant.id,  # Usar tenant_id explicitamente
            date__range=(start_date, end_date),
        ).order_by("date")
        logger.debug(
            f"Found {metrics.count()} metrics for tenant {tenant.id} "
            f"from {start_date} to {end_date}"
        )
        daily_series = [
            {
                "date": item.date.isoformat(),
                "minutes_total": float(item.minutes_total),
                "audio_count": item.audio_count,
                "success_count": item.success_count,
                "failed_count": item.failed_count,
                "quality_correct_count": item.quality_correct_count,
                "quality_incorrect_count": item.quality_incorrect_count,
                "quality_unrated_count": item.quality_unrated_count,
                "avg_latency_ms": float(item.avg_latency_ms) if item.avg_latency_ms is not None else None,
                "models_used": item.models_used or {},
            }
            for item in metrics
        ]
        totals = {
            "minutes_total": round(sum(item["minutes_total"] for item in daily_series), 2),
            "audio_count": sum(item["audio_count"] for item in daily_series),
            "success_count": sum(item["success_count"] for item in daily_series),
            "failed_count": sum(item["failed_count"] for item in daily_series),
            "quality_correct_count": sum(item["quality_correct_count"] for item in daily_series),
            "quality_incorrect_count": sum(item["quality_incorrect_count"] for item in daily_series),
            "quality_unrated_count": sum(item["quality_unrated_count"] for item in daily_series),
            "avg_latency_ms": None,
            "models_used": {},
        }
        
        # Calcular latência média geral
        latency_values = [item["avg_latency_ms"] for item in daily_series if item["avg_latency_ms"] is not None]
        if latency_values:
            totals["avg_latency_ms"] = round(sum(latency_values) / len(latency_values), 2)
        
        # Agregar modelos
        for item in daily_series:
            for model_name, count in (item["models_used"] or {}).items():
                totals["models_used"][model_name] = totals["models_used"].get(model_name, 0) + count

    avg_minutes_per_day = (
        round((totals["minutes_total"] / total_days), 2) if total_days > 0 else 0
    )

    return Response(
        {
            "range": {
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "timezone": "UTC",
            },
            "filters": {
                "department_id": str(department_id) if department_id else None,
                "agent_id": str(agent_id) if agent_id else None,
            },
            "totals": {
                **totals,
                "avg_minutes_per_day": avg_minutes_per_day,
            },
            "series": daily_series,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def transcription_quality_feedback(request, attachment_id):
    """Endpoint para feedback de qualidade da transcrição."""
    from apps.chat.models import MessageAttachment
    
    try:
        attachment = MessageAttachment.objects.get(
            id=attachment_id,
            tenant=request.user.tenant
        )
    except MessageAttachment.DoesNotExist:
        return Response(
            {"error": "Attachment não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    if not attachment.transcription:
        return Response(
            {"error": "Este attachment não possui transcrição."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    quality = request.data.get("quality")
    if quality not in ["correct", "incorrect"]:
        return Response(
            {"error": "quality deve ser 'correct' ou 'incorrect'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # ✅ Simplificar: salvar apenas qualidade e timestamp, sem user_id por enquanto
    # O campo transcription_quality_feedback_by é nullable, então podemos deixá-lo None
    # Isso evita problemas com conversão de UUID até identificarmos a causa raiz
    import logging
    logger = logging.getLogger(__name__)
    
    attachment.transcription_quality = quality
    attachment.transcription_quality_feedback_at = timezone.now()
    # ✅ Temporariamente deixar user como None para evitar erro de tipo
    # TODO: Investigar por que request.user.id retorna inteiro em vez de UUID
    attachment.transcription_quality_feedback_by = None
    
    try:
        attachment.save(update_fields=[
            "transcription_quality",
            "transcription_quality_feedback_at",
            "transcription_quality_feedback_by",
        ])
        logger.info(f"✅ Feedback de qualidade salvo: attachment={attachment_id}, quality={quality}")
    except Exception as e:
        logger.error(f"ERROR ao salvar attachment: {e}")
        return Response(
            {"error": f"Erro ao salvar feedback: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
    return Response({
        "status": "success",
        "attachment_id": str(attachment.id),
        "quality": quality,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def debug_transcription_attachments(request):
    """Endpoint temporário para debug - mostra estrutura de attachments com transcrição."""
    from apps.chat.models import MessageAttachment
    
    tenant = request.user.tenant
    limit = int(request.query_params.get('limit', 5))
    
    attachments = MessageAttachment.objects.filter(
        tenant=tenant,
        mime_type__startswith='audio/',
        transcription__isnull=False,
    ).exclude(transcription='')[:limit]
    
    debug_data = []
    for att in attachments:
        debug_data.append({
            'id': str(att.id),
            'created_at': att.created_at.isoformat(),
            'has_metadata': bool(att.metadata),
            'metadata_keys': list(att.metadata.keys()) if att.metadata else [],
            'has_ai_metadata': bool(att.ai_metadata),
            'ai_metadata_keys': list(att.ai_metadata.keys()) if att.ai_metadata else [],
            'metadata_duration_ms': att.metadata.get('duration_ms') if att.metadata else None,
            'metadata_duration': att.metadata.get('duration') if att.metadata else None,
            'ai_metadata_duration_ms': att.ai_metadata.get('duration_ms') if att.ai_metadata else None,
            'ai_metadata_duration': att.ai_metadata.get('duration') if att.ai_metadata else None,
            'transcription_data': att.ai_metadata.get('transcription') if att.ai_metadata else None,
        })
    
    return Response({
        'count': len(debug_data),
        'attachments': debug_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def rebuild_transcription_metrics_endpoint(request):
    """Endpoint admin para rebuild das métricas de transcrição."""
    tenant = request.user.tenant
    created_from = request.data.get("from")
    created_to = request.data.get("to")

    parsed_from = None
    if created_from:
        parsed_from = parse_datetime(created_from)
        if not parsed_from:
            parsed_date = parse_date(created_from)
            if parsed_date:
                parsed_from = datetime.combine(parsed_date, dt_time.min)
    
    parsed_to = None
    if created_to:
        parsed_to = parse_datetime(created_to)
        if not parsed_to:
            parsed_date = parse_date(created_to)
            if parsed_date:
                parsed_to = datetime.combine(parsed_date, dt_time.max)

    parsed_from = _ensure_aware(parsed_from) if parsed_from else None
    parsed_to = _ensure_aware(parsed_to) if parsed_to else None

    start_date, end_date = resolve_date_range(parsed_from, parsed_to)

    try:
        daily, totals = rebuild_transcription_metrics(tenant, start_date, end_date)
        return Response(
            {
                "status": "success",
                "message": f"Métricas rebuildadas de {start_date} até {end_date}",
                "range": {
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                },
                "totals": {
                    "minutes_total": round(totals["minutes_total"], 2),
                    "audio_count": totals["audio_count"],
                    "success_count": totals["success_count"],
                    "failed_count": totals["failed_count"],
                },
                "days_processed": len(daily),
            }
        )
    except Exception as exc:
        logger.error("Failed to rebuild transcription metrics", exc_info=True)
        return Response(
            {
                "status": "error",
                "error": str(exc),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ----- Conversation summaries (Gestão RAG) -----

from apps.ai.summary_rag import rag_upsert_for_summary, rag_remove_for_summary
from apps.ai.consolidation import (
    build_consolidated_content,
    consolidate_approved_summaries_for_contact,
    refresh_consolidation_for_contact,
)
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag


def _serialize_conversation_summary(item, contact_tags=None, is_consolidated=False):
    meta = item.metadata or {}
    status_val = item.status
    is_auto_approved = meta.get("auto_approved") is True
    is_auto_rejected = meta.get("auto_rejected") is True
    if status_val == ConversationSummary.STATUS_APPROVED and is_auto_approved:
        status_display = "Aprovado (automático)"
    elif status_val == ConversationSummary.STATUS_REJECTED and is_auto_rejected:
        status_display = "Reprovado (automático)"
    elif status_val == ConversationSummary.STATUS_APPROVED:
        status_display = "Aprovado"
    elif status_val == ConversationSummary.STATUS_REJECTED:
        status_display = "Reprovado"
    else:
        status_display = "Pendente"
    out = {
        "id": item.id,
        "conversation_id": str(item.conversation_id),
        "contact_phone": item.contact_phone or "",
        "contact_name": item.contact_name or "",
        "content": item.content or "",
        "metadata": meta,
        "status": status_val,
        "status_display": status_display,
        "is_auto_approved": is_auto_approved,
        "is_auto_rejected": is_auto_rejected,
        "is_consolidated": is_consolidated,
        "reviewed_at": timezone.localtime(item.reviewed_at).isoformat() if item.reviewed_at else None,
        "reviewed_by_id": item.reviewed_by_id,
        "created_at": timezone.localtime(item.created_at).isoformat(),
        "updated_at": timezone.localtime(item.updated_at).isoformat(),
    }
    if contact_tags is not None:
        out["contact_tags"] = contact_tags
    return out


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_list(request):
    """Lista resumos de conversa para gestão RAG (filtros: status, contact_phone, contact_name, from_date, to_date). Ordenação: mais recentes primeiro."""
    tenant = request.user.tenant
    queryset = ConversationSummary.objects.filter(tenant=tenant).order_by("-created_at")

    status_param = request.query_params.get("status")
    if status_param and status_param in (ConversationSummary.STATUS_PENDING, ConversationSummary.STATUS_APPROVED, ConversationSummary.STATUS_REJECTED):
        queryset = queryset.filter(status=status_param)

    contact_phone = request.query_params.get("contact_phone", "").strip()
    if contact_phone:
        queryset = queryset.filter(contact_phone__icontains=contact_phone)

    contact_name = request.query_params.get("contact_name", "").strip()
    if contact_name:
        queryset = queryset.filter(contact_name__icontains=contact_name)

    from_date = request.query_params.get("from_date")
    if from_date:
        parsed = parse_datetime(from_date) or (parse_date(from_date) and datetime.combine(parse_date(from_date), dt_time.min))
        if parsed:
            aware = _ensure_aware(parsed)
            if aware:
                queryset = queryset.filter(created_at__gte=aware)

    to_date = request.query_params.get("to_date")
    if to_date:
        parsed = parse_datetime(to_date) or (parse_date(to_date) and datetime.combine(parse_date(to_date), dt_time.max))
        if parsed:
            aware = _ensure_aware(parsed)
            if aware:
                queryset = queryset.filter(created_at__lte=aware)

    pagination = LimitOffsetPagination()
    pagination.default_limit = 20
    results = pagination.paginate_queryset(queryset, request)
    # IDs de resumos que estão em alguma consolidação (memória por contato)
    consolidated_summary_ids = set()
    for rec in ConsolidationRecord.objects.filter(tenant=tenant).values_list("summary_ids", flat=True):
        if isinstance(rec, list):
            consolidated_summary_ids.update(rec)
    # Resolver tags do contato por telefone (para exibir em vez do UUID na UI)
    contact_tags_by_phone = {}
    normalize_phone_for_search = None
    if results:
        from apps.contacts.models import Contact
        from apps.contacts.signals import normalize_phone_for_search as _norm
        normalize_phone_for_search = _norm
        phones = list({item.contact_phone for item in results if item.contact_phone})
        phones_for_query = set(phones) | {_norm(p) for p in phones}
        for c in Contact.objects.filter(tenant=tenant, phone__in=phones_for_query).prefetch_related("tags"):
            key_norm = _norm(c.phone)
            tag_names = [t.name for t in c.tags.all()]
            contact_tags_by_phone[key_norm] = tag_names
            contact_tags_by_phone[c.phone] = tag_names
    data = []
    for item in results:
        tags = []
        if item.contact_phone and normalize_phone_for_search:
            key = normalize_phone_for_search(item.contact_phone)
            tags = contact_tags_by_phone.get(key) or contact_tags_by_phone.get(item.contact_phone) or []
        data.append(_serialize_conversation_summary(item, contact_tags=tags, is_consolidated=(item.id in consolidated_summary_ids)))

    # Texto consolidado por contato (para exibir na mesma tela, só leitura)
    consolidated_content_by_contact = {}
    if results:
        contact_phones_in_page = {item.contact_phone for item in results if item.contact_phone}
        try:
            normalized_in_page = {normalize_contact_phone_for_rag(p) for p in contact_phones_in_page}
        except Exception as e:
            logger.warning(
                "Erro ao normalizar contact_phone para consolidação: %s", e
            )
            normalized_in_page = set()
        for rec in ConsolidationRecord.objects.filter(tenant=tenant).filter(
            contact_phone__in=normalized_in_page
        ):
            content = (getattr(rec, "content", None) or "").strip()
            summaries = []
            if not content:
                summary_ids_raw = rec.summary_ids
                summary_ids = summary_ids_raw if isinstance(summary_ids_raw, list) else []
                if not summary_ids:
                    continue
                ids_ints = []
                for sid in summary_ids:
                    try:
                        ids_ints.append(int(sid))
                    except (TypeError, ValueError):
                        continue
                if not ids_ints:
                    continue
                summaries = list(
                    ConversationSummary.objects.filter(
                        tenant=tenant,
                        id__in=ids_ints,
                        status=ConversationSummary.STATUS_APPROVED,
                    ).order_by("-created_at")
                )
                if not summaries:
                    continue
                content = build_consolidated_content(summaries)
            if not content:
                continue
            if summaries:
                for s in summaries:
                    key_phone = (s.contact_phone or rec.contact_phone or "").strip()
                    if key_phone:
                        consolidated_content_by_contact[key_phone] = content
            else:
                for p in contact_phones_in_page:
                    try:
                        if normalize_contact_phone_for_rag(p) == rec.contact_phone:
                            consolidated_content_by_contact[p] = content
                    except Exception as e:
                        logger.debug(
                            "Normalização ao preencher consolidated_content para %s: %s", p, e
                        )
            if rec.contact_phone and rec.contact_phone not in consolidated_content_by_contact:
                consolidated_content_by_contact[rec.contact_phone] = content

    response = pagination.get_paginated_response(data)
    response.data["consolidated_content_by_contact"] = consolidated_content_by_contact
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_consolidate(request):
    """Consolida resumos aprovados do mesmo contato em uma única memória RAG. Body: { \"summary_ids\": [1, 2, ...] }."""
    tenant = request.user.tenant
    data = request.data or {}
    summary_ids = data.get("summary_ids")
    if not isinstance(summary_ids, list) or len(summary_ids) < 2:
        return Response(
            {"error": "Envie summary_ids com pelo menos 2 IDs de resumos aprovados do mesmo contato."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        first_summary = ConversationSummary.objects.filter(tenant=tenant, id=summary_ids[0]).first()
        if not first_summary:
            return Response(
                {"error": "Resumo não encontrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contact_phone_normalized = normalize_contact_phone_for_rag(first_summary.contact_phone or "")
        if not contact_phone_normalized:
            return Response(
                {"error": "Não é possível consolidar resumos sem contato (contact_phone vazio)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _, summaries_count = consolidate_approved_summaries_for_contact(tenant.id, contact_phone_normalized, summary_ids=summary_ids)
        return Response({"ok": True, "message": "Resumos consolidados com sucesso.", "summaries_count": summaries_count})
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except RuntimeError as e:
        logger.exception("Consolidação falhou: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.exception("Consolidação falhou: %s", e)
        return Response({"error": "Erro ao consolidar. Tente novamente."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_consolidate_by_contact(request):
    """Consolida todos os resumos aprovados de um contato. Body: { \"contact_phone\": \"5511999999999\" }."""
    tenant = request.user.tenant
    data = request.data or {}
    contact_phone_raw = (data.get("contact_phone") or "").strip()
    if not contact_phone_raw:
        return Response(
            {"error": "Informe o telefone do contato."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    contact_phone_normalized = normalize_contact_phone_for_rag(contact_phone_raw)
    if not contact_phone_normalized:
        return Response(
            {"error": "Informe um telefone válido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        _, summaries_count = consolidate_approved_summaries_for_contact(tenant.id, contact_phone_normalized, summary_ids=None)
        return Response({
            "ok": True,
            "message": "Resumos consolidados com sucesso.",
            "summaries_count": summaries_count,
        })
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except RuntimeError as e:
        logger.exception("Consolidação por contato falhou: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.exception("Consolidação por contato falhou: %s", e)
        return Response({"error": "Erro ao consolidar. Tente novamente."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_consolidate_all(request):
    """Agrupa por contato e consolida cada um que tiver 2+ aprovados. Retorna contacts_consolidated e contacts_failed."""
    tenant = request.user.tenant
    all_approved = list(
        ConversationSummary.objects.filter(
            tenant_id=tenant.id,
            status=ConversationSummary.STATUS_APPROVED,
        ).order_by("-created_at")
    )
    by_contact = defaultdict(list)
    for s in all_approved:
        norm = normalize_contact_phone_for_rag(s.contact_phone or "")
        if norm:
            by_contact[norm].append(s)
    contacts_consolidated = 0
    contacts_failed = 0
    errors = []
    for contact_phone_normalized, summaries in by_contact.items():
        if len(summaries) < 2:
            continue
        try:
            consolidate_approved_summaries_for_contact(tenant.id, contact_phone_normalized, summary_ids=None)[0]
            contacts_consolidated += 1
        except Exception as e:
            contacts_failed += 1
            logger.warning("Consolidate-all: falha para contact_phone=%s: %s", contact_phone_normalized, e)
            errors.append({"contact_phone": contact_phone_normalized, "error": str(e)})
    return Response({
        "ok": True,
        "contacts_consolidated": contacts_consolidated,
        "contacts_failed": contacts_failed,
        "errors": errors[:20],
        "message": f"{contacts_consolidated} contato(s) consolidado(s)." + (f" {contacts_failed} falha(s)." if contacts_failed else ""),
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_detail(request, pk):
    """Aprovar, reprovar ou editar conteúdo de um resumo. Ao aprovar/editar aprovado envia rag-upsert; ao reprovar aprovado chama rag-remove."""
    tenant = request.user.tenant
    try:
        summary = ConversationSummary.objects.get(pk=pk, tenant=tenant)
    except ConversationSummary.DoesNotExist:
        return Response({"error": "Resumo não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    data = request.data or {}
    action = (data.get("action") or "").strip().lower()
    new_content = data.get("content")
    was_approved = summary.status == ConversationSummary.STATUS_APPROVED
    contact_normalized = normalize_contact_phone_for_rag(summary.contact_phone or "")

    if action == "approve":
        summary.status = ConversationSummary.STATUS_APPROVED
        summary.reviewed_at = timezone.now()
        summary.reviewed_by = request.user
        summary.updated_at = timezone.now()
        meta = dict(summary.metadata or {})
        meta.pop("auto_approved", None)
        summary.metadata = meta
        summary.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at", "metadata"])
        if ConsolidationRecord.objects.filter(tenant=tenant, contact_phone=contact_normalized).exists():
            refresh_consolidation_for_contact(tenant.id, summary.contact_phone)
        else:
            rag_upsert_for_summary(summary)
        return Response(_serialize_conversation_summary(summary))

    if action == "reject":
        summary.status = ConversationSummary.STATUS_REJECTED
        summary.reviewed_at = timezone.now()
        summary.reviewed_by = request.user
        summary.updated_at = timezone.now()
        summary.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])
        if ConsolidationRecord.objects.filter(tenant=tenant, contact_phone=contact_normalized).exists():
            refresh_consolidation_for_contact(tenant.id, summary.contact_phone)
        elif was_approved:
            rag_remove_for_summary(summary)
        return Response(_serialize_conversation_summary(summary))

    if action == "edit" and new_content is not None:
        content_str = (new_content if isinstance(new_content, str) else str(new_content)).strip()
        if not content_str:
            return Response({"error": "Conteúdo não pode ser vazio."}, status=status.HTTP_400_BAD_REQUEST)
        summary.content = content_str[:65535]
        summary.updated_at = timezone.now()
        meta = dict(summary.metadata or {})
        meta.pop("auto_approved", None)
        summary.metadata = meta
        summary.save(update_fields=["content", "updated_at", "metadata"])
        if summary.status == ConversationSummary.STATUS_APPROVED:
            if ConsolidationRecord.objects.filter(tenant=tenant, contact_phone=contact_normalized).exists():
                refresh_consolidation_for_contact(tenant.id, summary.contact_phone)
            else:
                rag_upsert_for_summary(summary)
        return Response(_serialize_conversation_summary(summary))

    return Response({"error": "Ação inválida. Use action: approve | reject | edit (com content para edit)."}, status=status.HTTP_400_BAD_REQUEST)


REPROCESS_BATCH_LIMIT = 10000

# ----- Reprocess job tracking (Redis) -----

REPROCESS_JOB_KEY_PREFIX = "reprocess_job:"
REPROCESS_JOB_TTL = 3600  # 1 hora


def _reprocess_job_set(job_id, tenant_id, user_id, total, notify_whatsapp_phone=None, notify_email=None):
    """Cria job de reprocessamento no Redis. Retorna True se ok, False se Redis indisponível."""
    client = get_redis_client()
    if not client:
        return False
    key = f"{REPROCESS_JOB_KEY_PREFIX}{job_id}"
    value = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "status": "running",
        "total": total,
        "processed": 0,
        "approved": 0,
        "rejected": 0,
        "started_at": timezone.now().isoformat(),
        "notify_whatsapp_phone": (notify_whatsapp_phone or "").strip() or None,
        "notify_email": (notify_email or "").strip() or None,
    }
    try:
        client.setex(key, REPROCESS_JOB_TTL, json.dumps(value))
        return True
    except Exception as e:
        logger.warning("[RAG] reprocess_job Redis set failed: %s", e)
        return False


def _reprocess_job_get(job_id):
    """Retorna dict do job ou None se não existir/Redis indisponível."""
    client = get_redis_client()
    if not client:
        return None
    key = f"{REPROCESS_JOB_KEY_PREFIX}{job_id}"
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning("[RAG] reprocess_job Redis get failed: %s", e)
        return None


def _reprocess_job_update(job_id, processed, approved, rejected, done=False):
    """Atualiza contadores do job no Redis."""
    client = get_redis_client()
    if not client:
        return
    key = f"{REPROCESS_JOB_KEY_PREFIX}{job_id}"
    try:
        raw = client.get(key)
        if not raw:
            return
        data = json.loads(raw)
        data["processed"] = processed
        data["approved"] = approved
        data["rejected"] = rejected
        if done:
            data["status"] = "done"
            data["finished_at"] = timezone.now().isoformat()
        client.setex(key, REPROCESS_JOB_TTL, json.dumps(data))
    except Exception as e:
        logger.warning("[RAG] reprocess_job Redis update failed: %s", e)


def _reprocess_send_report(tenant_id, notify_phone, notify_email, total, approved, rejected, started_at_iso):
    """Envia relatório de reprocessamento por WhatsApp e/ou email conforme solicitado. Erros são apenas logados."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    started_str = "?"
    if started_at_iso:
        try:
            dt = datetime.fromisoformat(started_at_iso.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            dt_gmt3 = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
            started_str = dt_gmt3.strftime("%d/%m/%Y %H:%M (GMT-3)")
        except Exception:
            pass
    percent = round(approved / total * 100, 1) if total > 0 else 0
    message = (
        f"✅ *Reprocessamento RAG concluído*\n\n"
        f"📊 Total processado: {total}\n"
        f"🟢 Aprovadas: {approved}  |  🔴 Reprovadas: {rejected}\n"
        f"📈 Taxa de sucesso: {percent}%\n\n"
        f"🕐 Iniciado em: {started_str}"
    )
    try:
        tid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
    except (ValueError, TypeError):
        logger.warning("[RAG] tenant_id inválido para envio de relatório: %s", tenant_id)
        return
    tenant = Tenant.objects.filter(id=tid).first()
    if not tenant:
        logger.warning("[RAG] Tenant %s não encontrado para envio de relatório", tenant_id)
        return
    if notify_phone:
        try:
            from apps.notifications.services import send_whatsapp_to_phone
            send_whatsapp_to_phone(tenant, notify_phone, message)
            logger.info("[RAG] Relatório WhatsApp enviado para %s", notify_phone)
        except Exception as e:
            logger.warning("[RAG] Falha ao enviar relatório WhatsApp: %s", e)
    if notify_email:
        try:
            from apps.notifications.models import SMTPConfig
            from django.core.mail import get_connection, EmailMessage as DjangoEmailMessage
            smtp = SMTPConfig.objects.filter(tenant=tenant, is_active=True, is_default=True).first()
            if not smtp:
                smtp = SMTPConfig.objects.filter(tenant=tenant, is_active=True).first()
            if smtp:
                conn = get_connection(
                    backend="django.core.mail.backends.smtp.EmailBackend",
                    host=smtp.get_smtp_host_resolved(),
                    port=smtp.port,
                    username=smtp.username,
                    password=smtp.password,
                    use_tls=smtp.use_tls,
                    use_ssl=smtp.use_ssl,
                    fail_silently=False,
                    timeout=30,
                )
                from_address = f"{smtp.from_name} <{smtp.from_email}>" if smtp.from_name else smtp.from_email
                email = DjangoEmailMessage(
                    subject="Reprocessamento RAG concluído",
                    body=message.replace("*", "").replace("|", "-"),
                    from_email=from_address,
                    to=[notify_email],
                    connection=conn,
                )
                email.send(fail_silently=False)
                logger.info("[RAG] Relatório email enviado para %s", notify_email)
            else:
                logger.warning("[RAG] SMTP não configurado para tenant %s", tenant_id)
        except Exception as e:
            logger.warning("[RAG] Falha ao enviar relatório email: %s", e)


def _reprocess_batch_worker(conv_ids, approved_map, job_id=None, user_id=None):
    """Um único thread processa o lote em sequência (evita dezenas de threads)."""
    from django.db import close_old_connections
    from apps.chat.conversation_summary_pipeline import _run_conversation_summary_pipeline_impl
    from apps.chat.models import Conversation

    close_old_connections()
    processed = 0
    approved_count = 0
    rejected_count = 0
    job_data = _reprocess_job_get(str(job_id)) if job_id else None
    started_at_iso = (job_data or {}).get("started_at")
    tenant_id = (job_data or {}).get("tenant_id")
    notify_phone = (job_data or {}).get("notify_whatsapp_phone") or ""
    notify_email = (job_data or {}).get("notify_email") or ""

    for conv_id in conv_ids:
        try:
            summary = approved_map.get(conv_id)
            if summary:
                rag_remove_for_summary(summary)
            conv = Conversation.objects.filter(id=conv_id).first()
            if conv and conv.metadata:
                meta = dict(conv.metadata)
                meta.pop("conversation_summary_at", None)
                conv.metadata = meta
                conv.save(update_fields=["metadata"])
            _run_conversation_summary_pipeline_impl(str(conv_id))
            # Determinar resultado lendo o ConversationSummary criado/atualizado
            if tenant_id:
                result_status = ConversationSummary.objects.filter(
                    tenant_id=tenant_id,
                    conversation_id=conv_id,
                ).values_list("status", flat=True).first()
                if result_status == ConversationSummary.STATUS_APPROVED:
                    approved_count += 1
                elif result_status == ConversationSummary.STATUS_REJECTED:
                    rejected_count += 1
        except Exception as e:
            logger.warning("[RAG] Erro ao reprocessar conversa %s: %s", conv_id, e)
        finally:
            processed += 1
            close_old_connections()
        if job_id:
            _reprocess_job_update(str(job_id), processed, approved_count, rejected_count)

    if job_id:
        _reprocess_job_update(str(job_id), processed, approved_count, rejected_count, done=True)

    # Enviar relatório apenas se foi solicitado (notify_phone e/ou notify_email)
    if tenant_id and (notify_phone or notify_email):
        try:
            _reprocess_send_report(
                tenant_id, notify_phone or None, notify_email or None,
                len(conv_ids), approved_count, rejected_count, started_at_iso,
            )
        except Exception as e:
            logger.warning("[RAG] Falha ao enviar relatório: %s", e)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_reprocess_notify_options(request):
    """Retorna opções de notificação para o modal de reprocessamento: has_smtp e has_whatsapp."""
    from apps.notifications.models import SMTPConfig
    from apps.notifications.services import _get_whatsapp_config_for_tenant
    tenant = request.user.tenant
    has_smtp = SMTPConfig.objects.filter(tenant=tenant, is_active=True).exists()
    base_url, api_key, _ = _get_whatsapp_config_for_tenant(tenant)
    has_whatsapp = bool(base_url and api_key)
    return Response({"has_smtp": has_smtp, "has_whatsapp": has_whatsapp})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_reprocess(request):
    """Reprocessa resumos: scope=all ou scope=contact (contact_phone obrigatório). Remove do pgvector se já aprovado; um thread processa o lote em sequência."""
    import re
    import threading
    from django.db import connection

    tenant = request.user.tenant
    data = request.data or {}
    scope = (data.get("scope") or "all").strip().lower()
    contact_phone = (data.get("contact_phone") or "").strip()

    if scope == "contact" and not contact_phone:
        return Response(
            {"error": "Para scope=contact é obrigatório informar contact_phone."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.chat.models import Conversation

    conversations_qs = Conversation.objects.filter(
        tenant=tenant,
        status="closed",
    ).exclude(contact_phone__contains="g.us")
    if scope == "contact":
        contact_phone_normalized = normalize_contact_phone_for_rag(contact_phone)
        if not contact_phone_normalized:
            return Response(
                {"error": "contact_phone inválido (informe apenas dígitos ou formato com DDI)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Match exato, com sufixo @s.whatsapp.net; em PostgreSQL também regex para prefixo de dígitos
        contact_q = (
            Q(contact_phone=contact_phone_normalized)
            | Q(contact_phone__startswith=contact_phone_normalized + "@")
        )
        if connection.vendor == "postgresql":
            safe_digits = re.escape(contact_phone_normalized)
            contact_q |= Q(contact_phone__regex=r"^" + safe_digits + r"([^0-9]|$)")
        conversations_qs = conversations_qs.filter(contact_q)

    summary_status = (data.get("summary_status") or "all").strip().lower()
    if summary_status not in ("all", "approved", "pending", "rejected"):
        summary_status = "all"
    if summary_status in ("approved", "pending", "rejected"):
        status_val = {
            "approved": ConversationSummary.STATUS_APPROVED,
            "pending": ConversationSummary.STATUS_PENDING,
            "rejected": ConversationSummary.STATUS_REJECTED,
        }[summary_status]
        conv_ids_with_status = set(
            ConversationSummary.objects.filter(tenant=tenant, status=status_val).values_list("conversation_id", flat=True)
        )
        conversations_qs = conversations_qs.filter(id__in=conv_ids_with_status)

    from apps.ai.models import TenantSecretaryProfile
    profile = TenantSecretaryProfile.objects.filter(tenant_id=tenant.id).first()
    if not profile or not getattr(profile, "use_memory", False):
        return Response(
            {"error": "Tenant sem use_memory ativo."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    total_eligible = conversations_qs.count()
    to_process = list(conversations_qs.values_list("id", flat=True)[:REPROCESS_BATCH_LIMIT])

    raw_phone = (data.get("notify_whatsapp_phone") or "").strip() or None
    raw_email = (data.get("notify_email") or "").strip() or None
    if raw_phone is not None and len(raw_phone) > 50:
        return Response(
            {"error": "notify_whatsapp_phone muito longo."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if raw_email is not None:
        if len(raw_email) > 254:
            return Response(
                {"error": "notify_email muito longo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", raw_email):
            return Response(
                {"error": "notify_email com formato inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    notify_whatsapp_phone = raw_phone
    notify_email = raw_email

    approved = {
        s.conversation_id: s
        for s in ConversationSummary.objects.filter(
            tenant=tenant,
            conversation_id__in=to_process,
            status=ConversationSummary.STATUS_APPROVED,
        )
    }

    job_id = None
    if to_process:
        job_id = uuid.uuid4()
        _reprocess_job_set(
            job_id, tenant.id, request.user.id, len(to_process),
            notify_whatsapp_phone=notify_whatsapp_phone,
            notify_email=notify_email,
        )
        thread = threading.Thread(
            target=_reprocess_batch_worker,
            args=(to_process, approved),
            kwargs={"job_id": job_id, "user_id": request.user.id},
            daemon=True,
        )
        thread.start()

    response_data = {
        "status": "success",
        "enqueued": len(to_process),
        "total_eligible": total_eligible,
    }
    if job_id:
        response_data["job_id"] = str(job_id)
    return Response(response_data)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_reprocess_status(request, job_id):
    """Retorna o status de um job de reprocessamento RAG pelo job_id (UUID)."""
    from datetime import datetime
    job = _reprocess_job_get(str(job_id))
    if not job:
        return Response({"error": "Job não encontrado ou expirado."}, status=status.HTTP_404_NOT_FOUND)
    if str(job.get("tenant_id")) != str(request.user.tenant.id):
        return Response({"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN)
    current_status = job.get("status", "running")
    # Detectar stale: ainda running mas started_at > 2h
    if current_status == "running":
        started_at_raw = job.get("started_at")
        if started_at_raw:
            try:
                started_dt = datetime.fromisoformat(started_at_raw)
                # Garantir aware para comparação com timezone.now()
                if started_dt.tzinfo is None:
                    started_dt = timezone.make_aware(started_dt)
                age_seconds = (timezone.now() - started_dt).total_seconds()
                if age_seconds > 7200:
                    current_status = "stale"
            except Exception:
                pass
    total = job.get("total") or 0
    approved = job.get("approved") or 0
    rejected = job.get("rejected") or 0
    processed = job.get("processed") or 0
    percent = round(approved / total * 100, 1) if total > 0 else 0
    notify_whatsapp_phone = job.get("notify_whatsapp_phone") or ""
    notify_email = job.get("notify_email") or ""
    return Response({
        "status": current_status,
        "total": total,
        "processed": processed,
        "approved": approved,
        "rejected": rejected,
        "percent": percent,
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "notify_whatsapp_requested": bool(notify_whatsapp_phone),
        "notify_email_requested": bool(notify_email),
    })


# ----- Aprovação automática (config por tenant) -----

from apps.ai.summary_auto_approve import CRITERION_DEFAULTS, REJECT_CRITERION_DEFAULTS


def _get_default_auto_approve_config():
    """Config padrão com todos os critérios e valores default."""
    criteria = {}
    for cid, spec in CRITERION_DEFAULTS.items():
        entry = {"enabled": False}
        if spec.get("type") == "number":
            entry["value"] = spec.get("default")
        criteria[cid] = entry
    return {"enabled": False, "criteria": criteria}


def _get_default_reject_config():
    """Config padrão para reprovação automática."""
    criteria = {}
    for cid, spec in REJECT_CRITERION_DEFAULTS.items():
        entry = {"enabled": False}
        if spec.get("type") == "number":
            entry["value"] = spec.get("default")
        criteria[cid] = entry
    return {"reject_enabled": False, "reject_criteria": criteria}


def _validate_auto_approve_config(data):
    """Valida e normaliza o config. Levanta ValueError com mensagem ou retorna dict limpo."""
    if not isinstance(data, dict):
        raise ValueError("Config deve ser um objeto.")
    enabled = data.get("enabled", False)
    criteria_raw = data.get("criteria")
    if criteria_raw is not None and not isinstance(criteria_raw, dict):
        raise ValueError("criteria deve ser um objeto.")
    criteria = {}
    for cid, c in (criteria_raw or {}).items():
        if cid not in CRITERION_DEFAULTS:
            continue
        spec = CRITERION_DEFAULTS[cid]
        entry = {"enabled": bool(c.get("enabled"))}
        if spec.get("type") == "number":
            try:
                v = c.get("value") if "value" in c else spec.get("default")
                v = float(v) if v is not None else spec.get("default")
            except (TypeError, ValueError):
                v = spec.get("default")
            if entry["enabled"] and v is not None:
                if cid == "min_words" and (v < 1 or v > 500):
                    raise ValueError("min_words deve estar entre 1 e 500.")
                if cid == "max_words" and (v < 50 or v > 2000):
                    raise ValueError("max_words deve estar entre 50 e 2000.")
                if cid == "satisfaction_min" and (v < 1 or v > 5):
                    raise ValueError("satisfaction_min deve estar entre 1 e 5.")
                if cid == "confidence_min" and (v < 0 or v > 1):
                    raise ValueError("confidence_min deve estar entre 0 e 1.")
                if cid == "min_messages" and (v < 1 or v > 100):
                    raise ValueError("min_messages deve estar entre 1 e 100.")
                entry["value"] = v
        criteria[cid] = entry
    if criteria.get("min_words", {}).get("enabled") and criteria.get("max_words", {}).get("enabled"):
        min_v = criteria["min_words"].get("value", CRITERION_DEFAULTS["min_words"]["default"])
        max_v = criteria["max_words"].get("value", CRITERION_DEFAULTS["max_words"]["default"])
        if max_v < min_v:
            raise ValueError("max_words deve ser >= min_words quando ambos estão ativos.")
    return {"enabled": bool(enabled), "criteria": criteria}


def _validate_reject_config(data):
    """Valida reject_enabled e reject_criteria. Retorna dict limpo ou levanta ValueError."""
    if not isinstance(data, dict):
        raise ValueError("reject config deve ser um objeto.")
    reject_enabled = data.get("reject_enabled", False)
    criteria_raw = data.get("reject_criteria")
    if criteria_raw is not None and not isinstance(criteria_raw, dict):
        raise ValueError("reject_criteria deve ser um objeto.")
    criteria = {}
    for cid, c in (criteria_raw or {}).items():
        if cid not in REJECT_CRITERION_DEFAULTS:
            continue
        spec = REJECT_CRITERION_DEFAULTS[cid]
        entry = {"enabled": bool(c.get("enabled"))}
        if spec.get("type") == "number":
            try:
                v = c.get("value") if "value" in c else spec.get("default")
                v = float(v) if v is not None else spec.get("default")
            except (TypeError, ValueError):
                v = spec.get("default")
            if entry["enabled"] and v is not None:
                if cid == "reject_confidence_below" and (v < 0 or v > 1):
                    raise ValueError("reject_confidence_below deve estar entre 0 e 1.")
                if cid == "reject_min_words_below" and (v < 1 or v > 500):
                    raise ValueError("reject_min_words_below deve estar entre 1 e 500.")
                entry["value"] = v
        criteria[cid] = entry
    for cid, spec in REJECT_CRITERION_DEFAULTS.items():
        if cid not in criteria:
            entry = {"enabled": False}
            if spec.get("type") == "number":
                entry["value"] = spec.get("default")
            criteria[cid] = entry
    return {"reject_enabled": bool(reject_enabled), "reject_criteria": criteria}


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def conversation_summary_auto_approve_config(request):
    """GET: retorna config de aprovação automática (com defaults). PATCH: atualiza config."""
    tenant = request.user.tenant
    profile = TenantSecretaryProfile.objects.filter(tenant=tenant).first()
    if not profile:
        return Response({"error": "Perfil da secretária não encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        try:
            raw = getattr(profile, "summary_auto_approve_config", None) or {}
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        default = _get_default_auto_approve_config()
        criteria = default.get("criteria", {}).copy()
        for cid, c in (raw.get("criteria") or {}).items():
            if cid in criteria:
                criteria[cid] = {**criteria[cid], **c}
        reject_default = _get_default_reject_config()
        reject_criteria = reject_default.get("reject_criteria", {}).copy()
        for cid, c in (raw.get("reject_criteria") or {}).items():
            if cid in reject_criteria:
                reject_criteria[cid] = {**reject_criteria[cid], **c}
        return Response({
            "enabled": raw.get("enabled", False),
            "criteria": criteria,
            "criterion_defaults": {k: {"label": v.get("label"), "type": v.get("type"), "default": v.get("default")} for k, v in CRITERION_DEFAULTS.items()},
            "reject_enabled": raw.get("reject_enabled", False),
            "reject_criteria": reject_criteria,
            "reject_criterion_defaults": {k: {"label": v.get("label"), "type": v.get("type"), "default": v.get("default")} for k, v in REJECT_CRITERION_DEFAULTS.items()},
        })

    # PATCH: merge with existing so missing keys (e.g. reject_*) are preserved
    data = request.data or {}
    try:
        existing = getattr(profile, "summary_auto_approve_config", None) or {}
        if not isinstance(existing, dict):
            existing = {}
        merge = {**existing}
        if "enabled" in data:
            merge["enabled"] = data["enabled"]
        if "criteria" in data:
            merge["criteria"] = data["criteria"]
        if "reject_enabled" in data:
            merge["reject_enabled"] = data["reject_enabled"]
        if "reject_criteria" in data:
            merge["reject_criteria"] = data["reject_criteria"]
        config = _validate_auto_approve_config({"enabled": merge.get("enabled"), "criteria": merge.get("criteria")})
        reject_config = _validate_reject_config({"reject_enabled": merge.get("reject_enabled"), "reject_criteria": merge.get("reject_criteria")})
        full_config = {**config, **reject_config}
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    profile.summary_auto_approve_config = full_config
    profile.save(update_fields=["summary_auto_approve_config", "updated_at"])
    return Response(full_config)


# ----- LibreChat agents proxy e agent-assignments -----

def _librechat_agents_proxy():
    """Chama GET LibreChat /api/agents/v1/models. Retorna (available, agents, error_message)."""
    base_url = (getattr(settings, "LIBRECHAT_URL", None) or "").strip().rstrip("/")
    api_key = (getattr(settings, "LIBRECHAT_API_KEY", None) or "").strip()
    if not base_url or not api_key:
        return False, [], "LibreChat não configurado (LIBRECHAT_URL ou LIBRECHAT_API_KEY vazio)."
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return False, [], "LIBRECHAT_URL deve usar http:// ou https://."
    url = f"{base_url}/api/agents/v1/models"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code >= 400:
            return False, [], (resp.text or f"HTTP {resp.status_code}")[:500]
        data = resp.json() if resp.content else None
        if data is None:
            return True, [], None
        # LibreChat models: pode vir em "data" (dict) ou como lista direta
        if isinstance(data, list):
            agents = data
        elif isinstance(data, dict):
            agents = data.get("data") if isinstance(data.get("data"), list) else []
        else:
            agents = []
        # Normalizar para { id, name } quando possível
        out = []
        for item in agents:
            if isinstance(item, dict):
                aid = item.get("id") or item.get("model") or ""
                name = (item.get("name") or item.get("id") or item.get("model") or str(aid)).strip() or str(aid)
                aid = str(aid).strip()
                if aid:
                    out.append({"id": aid, "name": name or aid})
            elif isinstance(item, str) and item.strip():
                out.append({"id": item.strip(), "name": item.strip()})
        return True, out, None
    except requests.Timeout:
        return False, [], "Timeout ao conectar ao LibreChat."
    except requests.RequestException as e:
        logger.warning("LibreChat agents proxy request error: %s", e, exc_info=True)
        return False, [], str(e) if str(e) else "Erro ao conectar ao LibreChat."
    except (ValueError, TypeError) as e:
        logger.warning("LibreChat agents proxy parse error: %s", e, exc_info=True)
        return False, [], "Resposta inválida do LibreChat."


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def librechat_agents(request):
    """GET: lista agentes disponíveis no LibreChat (proxy). Retorna { available, agents, error? }."""
    available, agents, err = _librechat_agents_proxy()
    payload = {"available": available, "agents": agents}
    if err:
        payload["error"] = err
    if not available:
        return Response(payload, status=status.HTTP_200_OK)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def librechat_health(request):
    """GET: health check do LibreChat. Retorna { ok: true } ou { ok: false, error: \"...\" }."""
    available, _, err = _librechat_agents_proxy()
    if available:
        return Response({"ok": True})
    return Response({"ok": False, "error": err or "LibreChat indisponível"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def secretary_metrics(request):
    """GET: contadores de respostas da secretária por origem (LibreChat vs n8n)."""
    librechat_total = cache.get("ai:secretary:librechat_total", 0)
    n8n_total = cache.get("ai:secretary:n8n_total", 0)
    return Response({
        "librechat_total": int(librechat_total) if librechat_total is not None else 0,
        "n8n_total": int(n8n_total) if n8n_total is not None else 0,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def agent_assignments_list(request):
    """GET: lista associações do tenant (Inbox + por departamento). Inclui department_name quando scope_type=department."""
    from django.db.utils import ProgrammingError, OperationalError
    from apps.authn.models import Department

    tenant = request.user.tenant
    try:
        assignments = AgentAssignment.objects.filter(tenant=tenant).order_by("scope_type", "scope_id")
    except (ProgrammingError, OperationalError):
        return Response([])
    dept_ids = [a.scope_id for a in assignments if a.scope_type == AgentAssignment.SCOPE_DEPARTMENT and a.scope_id]
    dept_map = {}
    if dept_ids:
        for d in Department.objects.filter(id__in=dept_ids):
            dept_map[str(d.id)] = d.name
    out = []
    for a in assignments:
        item = {
            "id": str(a.id),
            "scope_type": a.scope_type,
            "scope_id": str(a.scope_id) if a.scope_id else None,
            "librechat_agent_id": a.librechat_agent_id,
            "display_name": a.display_name,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        if a.scope_type == AgentAssignment.SCOPE_DEPARTMENT and a.scope_id:
            item["department_name"] = dept_map.get(str(a.scope_id)) or "Departamento removido"
        else:
            item["department_name"] = None
        out.append(item)
    return Response(out)


@api_view(["PUT", "PATCH", "POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def agent_assignment_upsert(request):
    """Cria ou atualiza associação por (scope_type, scope_id). scope_id obrigatório para department."""
    from django.db.utils import ProgrammingError, OperationalError
    from apps.authn.models import Department

    tenant = request.user.tenant
    data = request.data or {}
    scope_type = (data.get("scope_type") or "").strip().lower()
    if scope_type not in (AgentAssignment.SCOPE_INBOX, AgentAssignment.SCOPE_DEPARTMENT):
        return Response(
            {"error": "scope_type deve ser 'inbox' ou 'department'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    scope_id = data.get("scope_id")
    if scope_type == AgentAssignment.SCOPE_DEPARTMENT:
        if not scope_id:
            return Response({"error": "scope_id obrigatório para scope_type department."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            scope_id = uuid.UUID(str(scope_id))
            Department.objects.get(id=scope_id, tenant=tenant)
        except (Department.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Departamento não encontrado ou não pertence ao tenant."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        scope_id = None

    librechat_agent_id = (data.get("librechat_agent_id") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    if not librechat_agent_id:
        return Response({"error": "librechat_agent_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
    if not display_name:
        display_name = librechat_agent_id

    try:
        if scope_type == AgentAssignment.SCOPE_INBOX:
            assignment, created = AgentAssignment.objects.update_or_create(
                tenant=tenant,
                scope_type=AgentAssignment.SCOPE_INBOX,
                scope_id=None,
                defaults={"librechat_agent_id": librechat_agent_id, "display_name": display_name},
            )
        else:
            assignment, created = AgentAssignment.objects.update_or_create(
                tenant=tenant,
                scope_type=AgentAssignment.SCOPE_DEPARTMENT,
                scope_id=scope_id,
                defaults={"librechat_agent_id": librechat_agent_id, "display_name": display_name},
            )
        assignment.updated_at = timezone.now()
        assignment.save(update_fields=["updated_at"])
    except (ProgrammingError, OperationalError) as e:
        logger.warning("AgentAssignment upsert: tabela inexistente ou erro DB: %s", e)
        return Response(
            {"error": "Tabela de associações não disponível. Execute o script SQL docs/sql/ai/0016_agent_assignment.up.sql"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    out = {
        "id": str(assignment.id),
        "scope_type": assignment.scope_type,
        "scope_id": str(assignment.scope_id) if assignment.scope_id else None,
        "librechat_agent_id": assignment.librechat_agent_id,
        "display_name": assignment.display_name,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
        "updated_at": assignment.updated_at.isoformat() if assignment.updated_at else None,
    }
    if assignment.scope_type == AgentAssignment.SCOPE_DEPARTMENT and assignment.scope_id:
        try:
            dept = Department.objects.get(id=assignment.scope_id)
            out["department_name"] = dept.name
        except Department.DoesNotExist:
            out["department_name"] = "Departamento removido"
    else:
        out["department_name"] = None
    return Response(out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def agent_assignment_delete(request, assignment_id):
    """DELETE: remove associação por id."""
    from django.db.utils import ProgrammingError, OperationalError

    tenant = request.user.tenant
    try:
        assignment = AgentAssignment.objects.get(id=assignment_id, tenant=tenant)
    except (AgentAssignment.DoesNotExist, ValueError):
        return Response({"error": "Associação não encontrada."}, status=status.HTTP_404_NOT_FOUND)
    except (ProgrammingError, OperationalError):
        return Response({"error": "Tabela de associações não disponível."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    assignment.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


def _normalize_dify_input_schema(raw_schema: list) -> list:
    """
    Normaliza o user_input_form do Dify, cujo formato é uma lista de wrappers onde
    a chave é o tipo do campo:
      [{"text-input": {"label": "...", "variable": "...", "required": true}}, ...]
    Transforma em lista plana com campo "type" explícito:
      [{"type": "text-input", "label": "...", "variable": "...", "required": true}, ...]
    Campos sem estrutura reconhecida são ignorados para segurança.
    """
    result = []
    for wrapper in (raw_schema or []):
        if not isinstance(wrapper, dict):
            continue
        for field_type, field_data in wrapper.items():
            if isinstance(field_data, dict) and 'variable' in field_data:
                # field_type sempre prevalece sobre qualquer chave 'type' que possa vir dentro do field_data
                result.append({**field_data, 'type': field_type})
    return result


def _fetch_and_save_input_schema(item) -> list:
    """
    Busca user_input_form do agente Dify via GET /v1/parameters, normaliza o formato
    e salva em metadata['input_schema'].
    Falha silenciosamente (log warning) para nunca bloquear o cadastro.
    Retorna a lista de campos normalizada, ou [] em caso de erro/ausência.
    """
    import httpx as _httpx
    from urllib.parse import urlparse as _urlparse
    from django.utils import timezone as _tz
    try:
        parsed = _urlparse(item.public_url or '')
        if not (parsed.scheme and parsed.netloc):
            return []
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        api_key = (getattr(item, 'api_key_encrypted', '') or '').strip()
        if not api_key:
            return []
        with _httpx.Client(timeout=5) as client:
            resp = client.get(
                f"{base_url}/v1/parameters",
                headers={'Authorization': f'Bearer {api_key}'},
            )
        if resp.status_code != 200:
            logger.warning(
                "_fetch_and_save_input_schema: status %s para agente %s — schema nao sincronizado. body=%s",
                resp.status_code, getattr(item, 'id', '?'), resp.text[:200]
            )
            return []
        try:
            raw_schema = resp.json().get('user_input_form', [])
        except Exception as json_exc:
            logger.warning(
                "_fetch_and_save_input_schema: resposta nao-JSON para agente %s: %s — body=%s",
                getattr(item, 'id', '?'), json_exc, resp.text[:200]
            )
            return []
        schema = _normalize_dify_input_schema(raw_schema)
        meta = dict(item.metadata or {})
        meta['input_schema'] = schema
        item.metadata = meta
        item.updated_at = _tz.now()
        item.save(update_fields=['metadata', 'updated_at'])
        logger.info(
            "_fetch_and_save_input_schema: %d campos sincronizados para agente %s",
            len(schema), getattr(item, 'id', '?')
        )
        return schema
    except Exception as exc:
        logger.warning(
            "_fetch_and_save_input_schema falhou para agente %s: %s",
            getattr(item, 'id', '?'), exc
        )
        return []


def _dify_audit(
    tenant,
    user,
    action: str,
    scope_type: str | None = None,
    scope_id: uuid.UUID | None = None,
    catalog_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> None:
    try:
        DifyAuditLog.objects.create(
            tenant=tenant,
            user_id=(getattr(user, "id", None) if user else None),
            action=action,
            scope_type=scope_type,
            scope_id=scope_id,
            catalog_id=catalog_id,
            payload=payload or {},
        )
    except Exception as _audit_exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("dify_audit falhou (ação: %s): %s", action, _audit_exc)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def dify_settings(request):
    """GET/PATCH: settings do Dify por tenant (enabled/base_url)."""
    from django.db.utils import ProgrammingError, OperationalError

    tenant = request.user.tenant
    try:
        settings_obj, _ = DifySettings.objects.get_or_create(tenant=tenant)
    except (ProgrammingError, OperationalError):
        return Response(
            {"error": "Tabela Dify não disponível. Execute o script SQL docs/sql/ai/0017_dify_base_tables.up.sql"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if request.method == "GET":
        return Response(
            {
                "enabled": bool(getattr(settings_obj, "enabled", False)),
                "base_url": (getattr(settings_obj, "base_url", "") or ""),
                "api_key_source": "billing_tenant_product.api_key(slug=dify)",
            }
        )

    data = request.data or {}
    enabled_raw = data.get("enabled")
    enabled = _normalize_bool(enabled_raw)
    if enabled is None:
        enabled = bool(settings_obj.enabled)

    update_fields = ["enabled", "updated_at"]
    settings_obj.enabled = enabled

    # PATCH semântico: só atualiza base_url se explicitamente enviada
    # base_url_audit captura o valor atual para o audit log mesmo quando não alterada
    base_url_audit = settings_obj.base_url or ""
    if "base_url" in data:
        base_url_audit = str(data.get("base_url") or "").strip()
        if base_url_audit and not (base_url_audit.startswith("http://") or base_url_audit.startswith("https://")):
            return Response({"error": "base_url deve iniciar com http:// ou https://."}, status=status.HTTP_400_BAD_REQUEST)
        settings_obj.base_url = base_url_audit
        update_fields.append("base_url")

    settings_obj.updated_at = timezone.now()
    settings_obj.save(update_fields=update_fields)
    _dify_audit(tenant, request.user, "settings_update", payload={"enabled": enabled, "base_url": base_url_audit})

    return Response(
        {
            "enabled": bool(settings_obj.enabled),
            "base_url": settings_obj.base_url or "",
            "api_key_source": "billing_tenant_product.api_key(slug=dify)",
        }
    )


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def dify_catalog(request):
    """GET: lista catálogo; POST: cria item; PATCH: atualizar/ativar/desativar (soft-delete)."""
    from django.db.utils import ProgrammingError, OperationalError

    def _table_missing_response():
        return Response(
            {"error": "Tabela Dify não disponível. Execute o script SQL docs/sql/ai/0017_dify_base_tables.up.sql"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    tenant = request.user.tenant
    try:
        if request.method == "GET":
            items = DifyAppCatalogItem.objects.filter(tenant=tenant).order_by("-created_at")
            out = []
            for it in items:
                out.append(
                    {
                        "id": str(it.id),
                        "dify_app_id": it.dify_app_id,
                        "display_name": it.display_name,
                        "description": it.description or "",
                        "public_url": it.public_url or "",
                        "is_active": bool(it.is_active),
                        "has_api_key": bool(getattr(it, "api_key_encrypted", "") or ""),
                        "default_department_id": str(it.default_department_id) if it.default_department_id else None,
                        "whatsapp_instance_id": str(it.whatsapp_instance_id) if getattr(it, "whatsapp_instance_id", None) else None,
                        "metadata": it.metadata or {},
                        "input_schema": (it.metadata or {}).get('input_schema', []),
                        "default_inputs": it.default_inputs if hasattr(it, 'default_inputs') else {},
                        "created_at": it.created_at.isoformat() if it.created_at else None,
                        "updated_at": it.updated_at.isoformat() if it.updated_at else None,
                    }
                )
            return Response(out)
    except (ProgrammingError, OperationalError):
        return _table_missing_response()

    data = request.data or {}
    # Proteger POST e PATCH contra tabela inexistente
    try:
        DifyAppCatalogItem.objects.filter(tenant=tenant).exists()
    except (ProgrammingError, OperationalError):
        return _table_missing_response()
    if request.method == "POST":
        display_name = str(data.get("display_name") or "").strip()
        public_url = str(data.get("public_url") or "").strip()
        description = str(data.get("description") or "").strip()
        default_department_id = data.get("default_department_id")
        whatsapp_instance_id = data.get("whatsapp_instance_id")
        api_key = str(data.get("api_key") or "").strip()

        if not public_url:
            return Response({"error": "public_url é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        if not api_key:
            return Response({"error": "api_key é obrigatória."}, status=status.HTTP_400_BAD_REQUEST)

        # Extrair app_id da URL pública — esperado: https://dify.domain/chat/<app_id>
        dify_app_id = ""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(public_url)
            if not (parsed.scheme and parsed.netloc):
                return Response({"error": "public_url inválida."}, status=status.HTTP_400_BAD_REQUEST)
            parts = [p for p in (parsed.path or "").split("/") if p]
            if parts:
                dify_app_id = parts[-1]
        except Exception:
            dify_app_id = ""
        if not dify_app_id:
            return Response({"error": "Não foi possível extrair o app_id da URL pública."}, status=status.HTTP_400_BAD_REQUEST)
        # EC-B01: garantir que a URL tem formato esperado (/chat/<app_id>)
        # para evitar que URLs de API (ex: /v1/apps) criem agentes com IDs incorretos
        if "/chat/" not in public_url:
            return Response(
                {"error": "A URL pública deve conter /chat/<app_id>. Exemplo: https://dify.domain.com/chat/WjOslU"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not display_name:
            display_name = dify_app_id

        dept_uuid = None
        if default_department_id:
            dept_uuid = _parse_uuid(default_department_id)
            if not dept_uuid:
                return Response({"error": "default_department_id inválido."}, status=status.HTTP_400_BAD_REQUEST)

        wa_uuid = None
        if whatsapp_instance_id:
            wa_uuid = _parse_uuid(whatsapp_instance_id)
            if not wa_uuid:
                return Response({"error": "whatsapp_instance_id inválido."}, status=status.HTTP_400_BAD_REQUEST)

        item, created = DifyAppCatalogItem.objects.update_or_create(
            tenant=tenant,
            dify_app_id=dify_app_id,
            defaults={
                "display_name": display_name,
                "is_active": True,
                "public_url": public_url,
                "description": description,
                "default_department_id": dept_uuid,
                "whatsapp_instance_id": wa_uuid,
            },
        )
        # encrypt field cuida da criptografia em repouso
        item.api_key_encrypted = api_key
        item.updated_at = timezone.now()
        item.save(update_fields=["display_name", "is_active", "public_url", "description", "default_department_id", "whatsapp_instance_id", "api_key_encrypted", "updated_at"])

        # Auto-binding por departamento (opcional): se default_department_id foi definido,
        # faz upsert do vínculo do departamento para este catálogo.
        _binding_warning = None
        try:
            if item.default_department_id:
                DifyAssignment.objects.update_or_create(
                    tenant=tenant,
                    scope_type=DifyAssignment.SCOPE_DEPARTMENT,
                    scope_id=item.default_department_id,
                    defaults={"catalog": item},
                )
        except Exception as e:
            logger.error("DifyAssignment auto-binding (POST) falhou para agente %s: %s", item.id, e)
            _binding_warning = "Agente criado, mas o vínculo com o departamento não pôde ser salvo."
        _dify_audit(
            tenant,
            request.user,
            "catalog_create" if created else "catalog_update",
            catalog_id=item.id,
            payload={
                "dify_app_id": dify_app_id,
                "display_name": display_name,
                "has_api_key": bool(api_key),
                "default_department_id": str(dept_uuid) if dept_uuid else None,
            },
        )
        # Sincronizar schema de inputs do Dify (silencioso — nao bloqueia o cadastro)
        _post_input_schema = _fetch_and_save_input_schema(item)
        resp_data = {
            "id": str(item.id),
            "dify_app_id": item.dify_app_id,
            "display_name": item.display_name,
            "description": item.description or "",
            "public_url": item.public_url or "",
            "is_active": bool(item.is_active),
            "has_api_key": True,
            "default_department_id": str(item.default_department_id) if item.default_department_id else None,
            "whatsapp_instance_id": str(item.whatsapp_instance_id) if getattr(item, "whatsapp_instance_id", None) else None,
            "metadata": item.metadata or {},
            "input_schema": _post_input_schema,
            "default_inputs": item.default_inputs if hasattr(item, 'default_inputs') else {},
        }
        if _binding_warning:
            resp_data["warning"] = _binding_warning
        return Response(resp_data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    # PATCH
    item_id = _parse_uuid(data.get("id"))
    if not item_id:
        return Response({"error": "id (UUID) é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
    item = DifyAppCatalogItem.objects.filter(id=item_id, tenant=tenant).first()
    if not item:
        return Response({"error": "Item não encontrado."}, status=status.HTTP_404_NOT_FOUND)
    prev_default_dept_id = item.default_department_id
    if "display_name" in data:
        item.display_name = str(data.get("display_name") or "").strip()
    if "description" in data:
        item.description = str(data.get("description") or "").strip()
    if "public_url" in data:
        new_public_url = str(data.get("public_url") or "").strip()
        # E8: replicar validação do POST — /chat/ obrigatório para extrair dify_app_id correto
        if new_public_url and "/chat/" not in new_public_url:
            return Response(
                {"error": "A URL pública deve conter /chat/<app_id>. Exemplo: https://dify.domain.com/chat/WjOslU"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.public_url = new_public_url
        # EC-B10: reatualizar dify_app_id quando public_url é alterada
        if new_public_url:
            try:
                from urllib.parse import urlparse as _urlparse
                _parts = [p for p in (_urlparse(new_public_url).path or "").split("/") if p]
                if _parts:
                    item.dify_app_id = _parts[-1]
            except Exception:
                pass
    if "is_active" in data:
        b = _normalize_bool(data.get("is_active"))
        if b is None:
            return Response({"error": "is_active inválido."}, status=status.HTTP_400_BAD_REQUEST)
        item.is_active = b
    if "default_department_id" in data:
        dept_raw = data.get("default_department_id")
        if dept_raw:
            dept_uuid = _parse_uuid(dept_raw)
            if not dept_uuid:
                return Response({"error": "default_department_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
            item.default_department_id = dept_uuid
        else:
            item.default_department_id = None
    if "whatsapp_instance_id" in data:
        wa_raw = data.get("whatsapp_instance_id")
        if wa_raw:
            wa_uuid = _parse_uuid(wa_raw)
            if not wa_uuid:
                return Response({"error": "whatsapp_instance_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
            item.whatsapp_instance_id = wa_uuid
        else:
            item.whatsapp_instance_id = None
    patch_fields = ["display_name", "description", "public_url", "is_active", "default_department_id", "whatsapp_instance_id", "updated_at"]
    # dify_app_id só entra em patch_fields se public_url foi enviada (e portanto o app_id foi reextrado)
    if "public_url" in data:
        patch_fields.append("dify_app_id")
    api_key_raw = data.get("api_key")
    if api_key_raw is not None and str(api_key_raw).strip():
        # Só atualiza a chave se vier uma string não-vazia (evita apagar chave existente)
        item.api_key_encrypted = str(api_key_raw).strip()
        patch_fields.append("api_key_encrypted")
    # default_inputs: aceita qualquer dict; ignora se não enviado
    if "default_inputs" in data:
        raw_di = data.get("default_inputs")
        if isinstance(raw_di, dict):
            item.default_inputs = raw_di
            if 'default_inputs' not in patch_fields:
                patch_fields.append("default_inputs")
    item.updated_at = timezone.now()
    try:
        item.save(update_fields=patch_fields)
    except Exception as _save_exc:
        from django.db.utils import ProgrammingError, OperationalError
        if isinstance(_save_exc, (ProgrammingError, OperationalError)):
            return _table_missing_response()
        raise

    # Auto-binding por departamento (PATCH):
    # - Se setou dept padrão => upsert do vínculo desse dept
    # - Se removeu dept padrão => remove vínculo do dept anterior (se existir)
    try:
        if "default_department_id" in data:
            if prev_default_dept_id and not item.default_department_id:
                DifyAssignment.objects.filter(
                    tenant=tenant,
                    scope_type=DifyAssignment.SCOPE_DEPARTMENT,
                    scope_id=prev_default_dept_id,
                ).delete()
            if item.default_department_id:
                DifyAssignment.objects.update_or_create(
                    tenant=tenant,
                    scope_type=DifyAssignment.SCOPE_DEPARTMENT,
                    scope_id=item.default_department_id,
                    defaults={"catalog": item},
                )
    except Exception as e:
        logger.error("DifyAssignment auto-binding (PATCH) falhou para agente %s: %s", item.id, e)
        _patch_binding_warning = "Agente atualizado, mas o vínculo com o departamento não pôde ser salvo."
    else:
        _patch_binding_warning = None
    _dify_audit(
        tenant,
        request.user,
        "catalog_deactivate" if not item.is_active else "catalog_update",
        catalog_id=item.id,
        payload={"display_name": item.display_name, "is_active": bool(item.is_active)},
    )
    # Re-sincronizar schema quando public_url ou api_key forem alterados
    _patch_resync = "public_url" in data or (api_key_raw is not None and str(api_key_raw).strip())
    if _patch_resync:
        _patch_input_schema = _fetch_and_save_input_schema(item)
    else:
        _patch_input_schema = (item.metadata or {}).get('input_schema', [])
    patch_resp = {
        "id": str(item.id),
        "dify_app_id": item.dify_app_id,
        "display_name": item.display_name,
        "description": item.description or "",
        "public_url": item.public_url or "",
        "is_active": bool(item.is_active),
        "has_api_key": bool(getattr(item, "api_key_encrypted", "") or ""),
        "default_department_id": str(item.default_department_id) if item.default_department_id else None,
        "whatsapp_instance_id": str(item.whatsapp_instance_id) if getattr(item, "whatsapp_instance_id", None) else None,
        "metadata": item.metadata or {},
        "input_schema": _patch_input_schema,
        "default_inputs": item.default_inputs if hasattr(item, 'default_inputs') else {},
    }
    if _patch_binding_warning:
        patch_resp["warning"] = _patch_binding_warning
    return Response(patch_resp)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def dify_sync_schema(request):
    """
    POST /ai/dify/catalog/sync-schema/
    Body: { "catalog_id": "<uuid>" }
    Re-sincroniza o schema de inputs do agente Dify via /v1/parameters.
    Retorna { "input_schema": [...], "synced": true/false }.
    """
    from django.db.utils import ProgrammingError, OperationalError

    tenant = request.user.tenant
    data = request.data or {}
    catalog_id = _parse_uuid(data.get("catalog_id"))
    if not catalog_id:
        return Response({"error": "catalog_id (UUID) é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        item = DifyAppCatalogItem.objects.filter(id=catalog_id, tenant=tenant).first()
    except (ProgrammingError, OperationalError):
        return Response({"error": "Tabela Dify não disponível."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not item:
        return Response({"error": "Agente não encontrado."}, status=status.HTTP_404_NOT_FOUND)
    schema = _fetch_and_save_input_schema(item)
    # synced=True indica que a chamada ao Dify retornou algum resultado (mesmo vazio)
    # synced=False indica que houve falha (sem api_key, URL inválida, Dify offline)
    api_key = (getattr(item, 'api_key_encrypted', '') or '').strip()
    synced = bool(item.public_url and api_key)
    return Response({
        "input_schema": schema,
        "default_inputs": item.default_inputs if hasattr(item, 'default_inputs') else {},
        "synced": synced,
    })


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def dify_assignments(request):
    """GET: lista vínculos; PUT: upsert por (scope_type, scope_id)."""
    from django.db.utils import ProgrammingError, OperationalError
    from apps.authn.models import Department

    tenant = request.user.tenant
    if request.method == "GET":
        try:
            qs = (
                DifyAssignment.objects.select_related("catalog")
                .filter(tenant=tenant)
                .order_by("scope_type", "scope_id")
            )
            # Forçar avaliação dentro do try para capturar "relation does not exist"
            assignments = list(qs)
        except (ProgrammingError, OperationalError):
            return Response([])
        dept_ids = [
            a.scope_id
            for a in assignments
            if a.scope_type == DifyAssignment.SCOPE_DEPARTMENT and a.scope_id
        ]
        dept_map = {}
        if dept_ids:
            for d in Department.objects.filter(id__in=dept_ids):
                dept_map[str(d.id)] = d.name
        out = []
        for a in assignments:
            out.append(
                {
                    "id": str(a.id),
                    "scope_type": a.scope_type,
                    "scope_id": str(a.scope_id) if a.scope_id else None,
                    "catalog_id": str(a.catalog_id),
                    "catalog": {
                        "id": str(a.catalog_id),
                        "dify_app_id": a.catalog.dify_app_id,
                        "display_name": a.catalog.display_name,
                        "is_active": bool(a.catalog.is_active),
                    }
                    if a.catalog_id and a.catalog
                    else None,
                    "department_name": (dept_map.get(str(a.scope_id)) if a.scope_id else None),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                }
            )
        return Response(out)

    data = request.data or {}
    scope_type = str(data.get("scope_type") or "").strip().lower()
    if scope_type not in (DifyAssignment.SCOPE_INBOX, DifyAssignment.SCOPE_DEPARTMENT):
        return Response({"error": "scope_type deve ser 'inbox' ou 'department'."}, status=status.HTTP_400_BAD_REQUEST)
    scope_id = None
    if scope_type == DifyAssignment.SCOPE_DEPARTMENT:
        scope_id = _parse_uuid(data.get("scope_id"))
        if not scope_id:
            return Response({"error": "scope_id obrigatório para department."}, status=status.HTTP_400_BAD_REQUEST)
        if not Department.objects.filter(id=scope_id, tenant=tenant).exists():
            return Response({"error": "Departamento não encontrado ou não pertence ao tenant."}, status=status.HTTP_400_BAD_REQUEST)

    catalog_id = _parse_uuid(data.get("catalog_id"))
    if not catalog_id:
        return Response({"error": "catalog_id (UUID) é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
    catalog = DifyAppCatalogItem.objects.filter(id=catalog_id, tenant=tenant).first()
    if not catalog:
        return Response({"error": "Item do catálogo não encontrado."}, status=status.HTTP_400_BAD_REQUEST)
    if not getattr(catalog, "is_active", False):
        return Response({"error": "Item do catálogo está inativo."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        assignment, created = DifyAssignment.objects.update_or_create(
            tenant=tenant,
            scope_type=scope_type,
            scope_id=scope_id if scope_type == DifyAssignment.SCOPE_DEPARTMENT else None,
            defaults={"catalog": catalog},
        )
        assignment.updated_at = timezone.now()
        assignment.save(update_fields=["updated_at"])
    except (ProgrammingError, OperationalError) as e:
        logger.warning("DifyAssignment upsert erro DB: %s", e)
        return Response(
            {"error": "Tabela Dify não disponível. Execute o script SQL docs/sql/ai/0017_dify_base_tables.up.sql"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _dify_audit(
        tenant,
        request.user,
        "assignment_upsert",
        scope_type=scope_type,
        scope_id=scope_id,
        catalog_id=catalog.id,
        payload={"catalog_id": str(catalog.id), "dify_app_id": catalog.dify_app_id},
    )
    return Response(
        {
            "id": str(assignment.id),
            "scope_type": assignment.scope_type,
            "scope_id": str(assignment.scope_id) if assignment.scope_id else None,
            "catalog_id": str(assignment.catalog_id),
            "catalog": {
                "id": str(catalog.id),
                "dify_app_id": catalog.dify_app_id,
                "display_name": catalog.display_name,
                "is_active": bool(catalog.is_active),
            },
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def dify_test_connection(request):
    """
    Teste de conexão do Dify.

    Observação: a API key vem do billing_tenant_product.api_key (produto slug='dify').
    Este teste tenta chamar /v1/info no base_url configurado usando a API key,
    que valida conectividade + credencial (quando a key corresponde ao app).
    """
    tenant = request.user.tenant
    data = request.data or {}
    catalog_id = _parse_uuid(data.get("catalog_id"))

    base_url = ""
    api_key = ""

    from django.db.utils import ProgrammingError, OperationalError

    if catalog_id:
        try:
            item = DifyAppCatalogItem.objects.filter(id=catalog_id, tenant=tenant).first()
        except (ProgrammingError, OperationalError):
            return Response({"ok": False, "detail": "Tabela Dify não disponível."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not item:
            return Response({"ok": False, "detail": "Agente Dify não encontrado para este tenant."}, status=status.HTTP_400_BAD_REQUEST)
        # EC-B11: se o agente não tem public_url, retornar erro explícito ao invés
        # de silenciosamente testar a URL global (que pode ser de outro agente)
        if not (item.public_url or "").strip():
            return Response(
                {"ok": False, "detail": "Este agente não tem URL pública configurada. Edite o agente e salve a URL antes de testar."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from urllib.parse import urlparse

            parsed = urlparse(item.public_url)
            if parsed.scheme and parsed.netloc:
                base_url = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            pass
        if not base_url:
            return Response(
                {"ok": False, "detail": "URL pública do agente é inválida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        api_key = (getattr(item, "api_key_encrypted", "") or "").strip()
    else:
        try:
            settings_obj = DifySettings.objects.filter(tenant=tenant).first()
        except (ProgrammingError, OperationalError):
            return Response({"ok": False, "detail": "Tabela Dify não disponível."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        base_url = (getattr(settings_obj, "base_url", "") if settings_obj else "") or ""
        base_url = base_url.strip().rstrip("/")
        # Fallback: API key via billing_tenant_product (Tenant.get_product_api_key)
        try:
            api_key = (tenant.get_product_api_key("dify") or "").strip()
        except Exception:
            api_key = ""

    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        return Response({"ok": False, "detail": "Base URL do Dify não configurada."}, status=status.HTTP_400_BAD_REQUEST)
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return Response({"ok": False, "detail": "Base URL inválida (use http:// ou https://)."}, status=status.HTTP_400_BAD_REQUEST)

    if not api_key:
        return Response(
            {"ok": False, "detail": "API key não configurada para este agente/tenant."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # /v1/parameters usa a app API key (igual ao serviço de chat) — evita falso negativo com /v1/info
    url = f"{base_url}/v1/parameters"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code >= 400:
            detail = (resp.text or "")[:300]
            try:
                j = resp.json()
                if isinstance(j, dict):
                    detail = str(j.get("message") or j.get("error") or detail)[:300]
            except Exception:
                pass
            return Response({"ok": False, "detail": f"HTTP {resp.status_code}: {detail}"}, status=status.HTTP_200_OK)
        info = {}
        try:
            info = resp.json() if resp.content else {}
        except Exception:
            info = {}
        return Response({"ok": True, "detail": "Conexão OK.", "info": info}, status=status.HTTP_200_OK)
    except _httpx.TimeoutException:
        return Response({"ok": False, "detail": "Timeout ao conectar no Dify."}, status=status.HTTP_200_OK)
    except _httpx.RequestError as e:
        return Response({"ok": False, "detail": str(e) if str(e) else "Erro ao conectar no Dify."}, status=status.HTTP_200_OK)
