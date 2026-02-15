"""
Endpoint mestre para sync incremental de métricas de relatórios (todos os tenants).
Protegido por API key. Usado pelo n8n/cron para manter métricas atualizadas.
"""
import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from apps.tenancy.models import Tenant
from apps.chat.models import (
    Conversation,
    ChatMessageDailyMetric,
    Message,
    MessageAttachment,
)
from apps.chat.message_metrics import aggregate_message_metrics_for_date
from apps.ai.models import AiTranscriptionDailyMetric
from apps.ai.transcription_metrics import rebuild_transcription_metrics

logger = logging.getLogger(__name__)

MAX_DAYS_FIRST_RUN = 730
DEFAULT_DAYS_FIRST_RUN = 90


def _validate_api_key(request):
    """Valida API key do header X-API-Key ou Authorization Bearer."""
    configured = getattr(settings, "REPORTS_SYNC_API_KEY", "") or ""
    if not configured:
        return False, "Endpoint desabilitado (REPORTS_SYNC_API_KEY não configurada)"
    provided = (
        request.headers.get("X-API-Key")
        or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    )
    if not provided:
        return False, "API key ausente"
    if not secrets.compare_digest(configured, provided):
        return False, "API key inválida"
    return True, None


def _get_message_metrics_range(tenant):
    """Retorna (start_date, end_date) para métricas de mensagens do tenant."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    max_row = (
        ChatMessageDailyMetric.objects.filter(
            tenant=tenant, department__isnull=True
        ).aggregate(max_date=Max("date"))
    )
    max_date = max_row.get("max_date")

    if max_date is None:
        first_msg = (
            Message.objects.filter(conversation__tenant=tenant)
            .aggregate(min_created=Min("created_at"))
        )
        min_created = first_msg.get("min_created")
        if min_created:
            start = min_created.date() if hasattr(min_created, "date") else min_created
        else:
            start = today - timedelta(days=DEFAULT_DAYS_FIRST_RUN)
        limit = today - timedelta(days=MAX_DAYS_FIRST_RUN)
        if start < limit:
            start = limit
    else:
        start = max_date + timedelta(days=1)

    if start > yesterday:
        return None, None
    return start, yesterday


def _get_transcription_metrics_range(tenant):
    """Retorna (start_date, end_date) para métricas de transcrição do tenant."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    max_row = AiTranscriptionDailyMetric.objects.filter(tenant_id=tenant.id).aggregate(
        max_date=Max("date")
    )
    max_date = max_row.get("max_date")

    if max_date is None:
        first_audio = (
            MessageAttachment.objects.filter(
                tenant_id=tenant.id, mime_type__startswith="audio/"
            ).aggregate(min_created=Min("created_at"))
        )
        min_created = first_audio.get("min_created")
        if min_created:
            start = min_created.date() if hasattr(min_created, "date") else min_created
        else:
            start = today - timedelta(days=DEFAULT_DAYS_FIRST_RUN)
        limit = today - timedelta(days=MAX_DAYS_FIRST_RUN)
        if start < limit:
            start = limit
    else:
        start = max_date + timedelta(days=1)

    if start > yesterday:
        return None, None
    return start, yesterday


def _sync_message_metrics(tenant, start, end):
    """Sincroniza métricas de mensagens para o tenant no range [start, end]."""
    conv_qs = Conversation.objects.filter(tenant=tenant)
    current = start
    days_processed = 0
    total_count = sent_count = received_count = 0

    while current <= end:
        data = aggregate_message_metrics_for_date(conv_qs, current)
        with transaction.atomic():
            ChatMessageDailyMetric.objects.update_or_create(
                tenant=tenant,
                date=current,
                department=None,
                defaults={
                    "total_count": data["total_count"],
                    "sent_count": data["sent_count"],
                    "received_count": data["received_count"],
                    "series_by_hour": data["series_by_hour"],
                    "avg_first_response_seconds": data["avg_first_response_seconds"],
                    "by_user": data["by_user"],
                },
            )
        total_count += data["total_count"]
        sent_count += data["sent_count"]
        received_count += data["received_count"]
        days_processed += 1
        current += timedelta(days=1)

    return {
        "days_processed": days_processed,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "totals": {"total": total_count, "sent": sent_count, "received": received_count},
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def reports_sync_incremental(request):
    """
    POST /api/chat/reports/sync/incremental/
    Header: X-API-Key: <REPORTS_SYNC_API_KEY>

    Processa todos os tenants: métricas de mensagens e transcrição (incremental).
    Se o tenant não tem métricas ainda, processa do zero.
    """
    valid, err_msg = _validate_api_key(request)
    if not valid:
        if "desabilitado" in (err_msg or ""):
            return Response({"error": err_msg}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"error": err_msg}, status=status.HTTP_401_UNAUTHORIZED)

    synced_at = timezone.now().isoformat()
    tenants_qs = Tenant.objects.filter(status__in=["active", "trial"]).order_by("name")
    results = []
    tenants_ok = 0
    tenants_failed = 0

    for tenant in tenants_qs:
        result = {
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "messages": None,
            "transcription": None,
            "error": None,
        }

        try:
            start_msg, end_msg = _get_message_metrics_range(tenant)
            if start_msg is not None and end_msg is not None:
                result["messages"] = _sync_message_metrics(tenant, start_msg, end_msg)
                logger.info(
                    f"[REPORTS SYNC] Tenant {tenant.name}: messages {start_msg}->{end_msg}"
                )

            start_tr, end_tr = _get_transcription_metrics_range(tenant)
            if start_tr is not None and end_tr is not None:
                daily, totals = rebuild_transcription_metrics(tenant, start_tr, end_tr)
                result["transcription"] = {
                    "days_processed": len(daily),
                    "from": start_tr.isoformat(),
                    "to": end_tr.isoformat(),
                    "totals": {
                        "minutes_total": round(totals.get("minutes_total", 0), 2),
                        "audio_count": totals.get("audio_count", 0),
                    },
                }
                logger.info(
                    f"[REPORTS SYNC] Tenant {tenant.name}: transcription {start_tr}->{end_tr}"
                )

            tenants_ok += 1
        except Exception as e:
            logger.exception(f"[REPORTS SYNC] Erro no tenant {tenant.name}: {e}")
            result["error"] = "Erro ao processar métricas"
            tenants_failed += 1

        results.append(result)

    return Response(
        {
            "status": "success",
            "synced_at": synced_at,
            "tenants_total": len(results),
            "tenants_ok": tenants_ok,
            "tenants_failed": tenants_failed,
            "results": results,
        },
        status=status.HTTP_200_OK,
    )
