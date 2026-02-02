import logging
import re
import uuid
import requests

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from django.conf import settings
from django.utils import timezone

# from .tasks import analyze_message_async  # Removido - Celery deletado
from apps.chat_messages.models import Message
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.ai.models import AiTriageResult, TenantAiSettings
from apps.ai.triage_service import run_test_prompt, run_transcription_test
from apps.chat.utils.s3 import get_s3_manager, get_public_url

logger = logging.getLogger(__name__)


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

    payload = {
        "action": "chat",
        "message": request.data.get("message", ""),
        "context": request.data.get("context", {}),
        "model": settings_obj.agent_model,
    }

    try:
        response = requests.post(ai_webhook, json=payload, timeout=10.0)
        response.raise_for_status()
        return Response({"status": "success", "data": response.json() if response.content else {}})
    except Exception as exc:
        return Response(
            {"status": "error", "error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
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
