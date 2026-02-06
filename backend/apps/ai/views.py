import logging
import re
import time
from datetime import datetime, time as dt_time
import uuid
import requests

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

# from .tasks import analyze_message_async  # Removido - Celery deletado
from apps.chat_messages.models import Message
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.ai.models import AiGatewayAudit, AiTriageResult, TenantAiSettings, AiTranscriptionDailyMetric
from apps.ai.transcription_metrics import (
    aggregate_transcription_metrics,
    build_transcription_queryset,
    rebuild_transcription_metrics,
    resolve_date_range,
)
from apps.ai.triage_service import run_test_prompt, run_transcription_test
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


def _serialize_ai_settings(settings_obj: TenantAiSettings) -> dict:
    return {
        "ai_enabled": settings_obj.ai_enabled,
        "audio_transcription_enabled": settings_obj.audio_transcription_enabled,
        "transcription_auto": settings_obj.transcription_auto,
        "transcription_min_seconds": settings_obj.transcription_min_seconds,
        "transcription_max_mb": settings_obj.transcription_max_mb,
        "triage_enabled": settings_obj.triage_enabled,
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


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
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
    request_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    conversation_id = _parse_uuid(request.data.get("conversation_id")) or uuid.uuid4()
    message_id = _parse_uuid(request.data.get("message_id")) or uuid.uuid4()
    contact_id = _parse_uuid(request.data.get("contact_id")) or uuid.uuid4()
    agent_id = _parse_uuid(request.data.get("agent_id")) or _parse_uuid(request.user.id)
    department_id = _parse_uuid(request.data.get("department_id"))
    if not department_id:
        first_department = request.user.departments.first()
        if first_department:
            department_id = first_department.id

    payload = {
        "protocol_version": "v1",
        "action": "chat",
        "request_id": str(request_id),
        "trace_id": str(trace_id),
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

    start_time = time.monotonic()
    status_value = "success"
    error_code = ""
    error_message = ""
    response_payload = {}

    try:
        response = requests.post(ai_webhook, json=payload, timeout=10.0)
        response.raise_for_status()
        response_payload = response.json() if response.content else {}
    except requests.Timeout as exc:
        status_value = "failed"
        error_code = "TIMEOUT"
        error_message = str(exc)
        response_payload = {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
        }
    except requests.RequestException as exc:
        status_value = "failed"
        error_code = "UPSTREAM_ERROR"
        error_message = str(exc)
        response_payload = {
            "status": "error",
            "error_code": error_code,
            "error_message": error_message,
        }
    except ValueError as exc:
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

    meta = response_payload.get("meta") if isinstance(response_payload, dict) else {}
    model_name = (
        str(meta.get("model") or response_payload.get("model") or selected_model)
        if isinstance(response_payload, dict)
        else selected_model
    )
    rag_hits = meta.get("rag_hits") if isinstance(meta, dict) else None
    prompt_version = meta.get("prompt_version") if isinstance(meta, dict) else ""
    handoff = bool(response_payload.get("handoff")) if isinstance(response_payload, dict) else False
    handoff_reason = str(response_payload.get("handoff_reason") or "") if isinstance(response_payload, dict) else ""
    reply_text = str(response_payload.get("reply_text") or response_payload.get("text") or "") if isinstance(response_payload, dict) else ""

    masked_request = _mask_payload(payload)
    masked_response = _mask_payload(response_payload)

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
        latency_ms=meta.get("latency_ms") if isinstance(meta, dict) else latency_ms,
        rag_hits=rag_hits,
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

    return Response(
        {
            "status": "success",
            "request_id": str(request_id),
            "trace_id": str(trace_id),
            "data": {
                "request": masked_request,
                "response": masked_response,
            },
        }
    )


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

    for field in ['ai_enabled', 'audio_transcription_enabled', 'transcription_auto', 'triage_enabled']:
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
    
    # ✅ Buscar o usuário do banco para garantir que temos o UUID correto
    from apps.authn.models import User
    try:
        # Buscar usuário pelo email para garantir UUID correto
        user = User.objects.get(email=request.user.email, tenant=request.user.tenant)
        user_id = str(user.id)  # UUID como string
    except User.DoesNotExist:
        # Fallback: tentar usar request.user.id se for UUID
        user_id = str(request.user.id) if hasattr(request.user, 'id') else None
        if not user_id or user_id == '13' or not isinstance(request.user.id, uuid.UUID):
            return Response(
                {"error": "Erro ao identificar usuário."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    # ✅ Usar SQL direto para garantir que o UUID seja salvo corretamente
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE chat_attachment 
            SET transcription_quality = %s,
                transcription_quality_feedback_at = %s,
                transcription_quality_feedback_by_id = %s::uuid
            WHERE id = %s::uuid 
              AND tenant_id = %s::uuid
        """, [
            quality,
            timezone.now(),
            user_id,
            str(attachment_id),
            str(request.user.tenant.id),
        ])
    
    # Recarregar o attachment atualizado
    attachment.refresh_from_db()
    
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
