import json
import logging
import re
import time
from datetime import datetime, time as dt_time
import uuid
import requests

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

# from .tasks import analyze_message_async  # Removido - Celery deletado
from apps.chat.models import Conversation, Message as ChatMessage
from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.ai.models import (
    AiGatewayAudit,
    AiTriageResult,
    TenantAiSettings,
    TenantSecretaryProfile,
    AiTranscriptionDailyMetric,
    ConversationSummary,
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
from apps.ai.secretary_service import build_secretary_payload_for_test, _server_time_utc_iso
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

    simulate_production = request.data.get("simulate_production") is True
    if simulate_production:
        logger.info(
            "[GATEWAY TEST] simulate_production=true: enviando payload secretary (RAG, business_hours, company_context)"
        )
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
    summary_for_department = (request.data.get("summary_for_department") or "").strip()[:2000]

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
            "created_at": timezone.localtime(profile.created_at).isoformat(),
            "updated_at": timezone.localtime(profile.updated_at).isoformat(),
        })
    # PUT
    data = request.data or {}
    profile, _ = TenantSecretaryProfile.objects.get_or_create(tenant=tenant)
    errors = {}

    if 'form_data' in data:
        fd = data.get('form_data')
        logger.info(
            "[SECRETARY PROFILE PUT] Recebido form_data: keys=%s, tamanho=%s, dados=%s",
            list(fd.keys()) if isinstance(fd, dict) else 'N/A',
            len(str(fd)) if fd else 0,
            fd  # Log completo dos dados recebidos
        )
        sanitized, err = _validate_secretary_form_data(fd)
        if err:
            errors['form_data'] = err
            logger.warning("[SECRETARY PROFILE PUT] Erro na validação: %s", err)
        else:
            logger.info(
                "[SECRETARY PROFILE PUT] form_data sanitizado: keys=%s, tamanho=%s, dados=%s",
                list(sanitized.keys()) if isinstance(sanitized, dict) else 'N/A',
                len(str(sanitized)) if sanitized else 0,
                sanitized  # Log completo dos dados sanitizados
            )
            # ✅ LOG ESPECÍFICO: Verificar se email e business_area estão presentes
            if isinstance(sanitized, dict):
                logger.info(
                    "[SECRETARY PROFILE PUT] Campos específicos: email=%s, business_area=%s",
                    sanitized.get('email', 'NÃO ENVIADO'),
                    sanitized.get('business_area', 'NÃO ENVIADO')
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


def _serialize_conversation_summary(item, contact_tags=None):
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
    """Lista resumos de conversa para gestão RAG (filtros: status, contact_phone, contact_name, from_date, to_date). Ordenação: nome do contato A->Z, depois mais recente."""
    tenant = request.user.tenant
    queryset = ConversationSummary.objects.filter(tenant=tenant).order_by(Lower("contact_name"), "-created_at")

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
        data.append(_serialize_conversation_summary(item, contact_tags=tags))
    return pagination.get_paginated_response(data)


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

    if action == "approve":
        summary.status = ConversationSummary.STATUS_APPROVED
        summary.reviewed_at = timezone.now()
        summary.reviewed_by = request.user
        summary.updated_at = timezone.now()
        meta = dict(summary.metadata or {})
        meta.pop("auto_approved", None)
        summary.metadata = meta
        summary.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at", "metadata"])
        rag_upsert_for_summary(summary)
        return Response(_serialize_conversation_summary(summary))

    if action == "reject":
        if was_approved:
            rag_remove_for_summary(summary)
        summary.status = ConversationSummary.STATUS_REJECTED
        summary.reviewed_at = timezone.now()
        summary.reviewed_by = request.user
        summary.updated_at = timezone.now()
        summary.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])
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
                    host=smtp.host,
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

from apps.ai.summary_auto_approve import CRITERION_DEFAULTS


def _get_default_auto_approve_config():
    """Config padrão com todos os critérios e valores default."""
    criteria = {}
    for cid, spec in CRITERION_DEFAULTS.items():
        entry = {"enabled": False}
        if spec.get("type") == "number":
            entry["value"] = spec.get("default")
        criteria[cid] = entry
    return {"enabled": False, "criteria": criteria}


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
        return Response({
            "enabled": raw.get("enabled", False),
            "criteria": criteria,
            "criterion_defaults": {k: {"label": v.get("label"), "type": v.get("type"), "default": v.get("default")} for k, v in CRITERION_DEFAULTS.items()},
        })

    # PATCH
    data = request.data or {}
    try:
        config = _validate_auto_approve_config(data)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    profile.summary_auto_approve_config = config
    profile.save(update_fields=["summary_auto_approve_config", "updated_at"])
    return Response(config)
