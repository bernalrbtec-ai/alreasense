from datetime import date as date_type, datetime, time as dt_time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import (
    BigIntegerField,
    Case,
    Count,
    ExpressionWrapper,
    FloatField,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, TruncDate
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from apps.ai.models import AiTranscriptionDailyMetric
from apps.chat.models import MessageAttachment


DEFAULT_RANGE_DAYS = 30
MINUTES_DIVISOR = Decimal("60000")


def _success_filter() -> Q:
    return Q(transcription__isnull=False) & ~Q(transcription="")


def _failed_filter() -> Q:
    return Q(processing_status="failed")


def _duration_filter() -> Q:
    return (
        Q(metadata__duration_ms__isnull=False)
        | Q(ai_metadata__duration_ms__isnull=False)
        | Q(metadata__duration__isnull=False)
        | Q(ai_metadata__duration__isnull=False)
    )


def _duration_ms_expression():
    duration_ms_metadata = Cast(KeyTextTransform("duration_ms", "metadata"), BigIntegerField())
    duration_ms_ai = Cast(KeyTextTransform("duration_ms", "ai_metadata"), BigIntegerField())
    duration_seconds_metadata = Cast(KeyTextTransform("duration", "metadata"), FloatField())
    duration_seconds_ai = Cast(KeyTextTransform("duration", "ai_metadata"), FloatField())
    duration_seconds_metadata_ms = ExpressionWrapper(
        duration_seconds_metadata * Value(1000.0),
        output_field=BigIntegerField(),
    )
    duration_seconds_ai_ms = ExpressionWrapper(
        duration_seconds_ai * Value(1000.0),
        output_field=BigIntegerField(),
    )
    return Coalesce(
        duration_ms_metadata,
        duration_ms_ai,
        duration_seconds_metadata_ms,
        duration_seconds_ai_ms,
    )


def _normalize_date(value) -> date_type:
    if isinstance(value, datetime):
        return value.date()
    return value


def resolve_date_range(created_from=None, created_to=None):
    today = timezone.now().date()
    if created_to:
        end_date = _normalize_date(created_to)
    else:
        end_date = today
    if created_from:
        start_date = _normalize_date(created_from)
    else:
        start_date = end_date - timedelta(days=DEFAULT_RANGE_DAYS)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def build_transcription_queryset(tenant, created_from, created_to, department_id=None, agent_id=None):
    queryset = MessageAttachment.objects.select_related(
        "message",
        "message__conversation",
    ).filter(
        tenant=tenant,
        mime_type__startswith="audio/",
    )

    if created_from:
        queryset = queryset.filter(created_at__gte=created_from)
    if created_to:
        queryset = queryset.filter(created_at__lte=created_to)
    if department_id:
        queryset = queryset.filter(message__conversation__department_id=department_id)
    if agent_id:
        queryset = queryset.filter(message__conversation__assigned_to_id=agent_id)
    return queryset


def _extract_duration_ms_from_attachment(attachment) -> int:
    """Extrai duration_ms de um attachment usando a mesma lógica do triage_service."""
    # Tentar metadata primeiro
    if attachment.metadata:
        duration_ms = attachment.metadata.get('duration_ms')
        if duration_ms is not None:
            return int(duration_ms)
        duration = attachment.metadata.get('duration')
        if duration is not None:
            return int(float(duration) * 1000)
    
    # Tentar ai_metadata
    if attachment.ai_metadata:
        duration_ms = attachment.ai_metadata.get('duration_ms')
        if duration_ms is not None:
            return int(duration_ms)
        duration = attachment.ai_metadata.get('duration')
        if duration is not None:
            return int(float(duration) * 1000)
    
    return 0


def aggregate_transcription_metrics(queryset, start_date, end_date, tzinfo=timezone.utc):
    """Agrega métricas processando em Python para garantir extração correta de duration."""
    success_filter = _success_filter()
    failed_filter = _failed_filter()

    # Agrupar por dia usando SQL para contagens
    rows = (
        queryset.annotate(day=TruncDate("created_at", tzinfo=tzinfo))
        .values("day")
        .annotate(
            success_count=Count("id", filter=success_filter),
            failed_count=Count("id", filter=failed_filter),
        )
    )

    # Inicializar métricas por dia
    metrics_by_day = {}
    for row in rows:
        day = row["day"]
        metrics_by_day[day] = {
            "success_count": row["success_count"],
            "failed_count": row["failed_count"],
            "duration_ms_total": 0,
        }
    
    # Buscar todos os attachments com sucesso e calcular duration_ms em Python
    success_attachments = queryset.filter(success_filter).only(
        'id', 'metadata', 'ai_metadata', 'created_at'
    )
    
    for attachment in success_attachments:
        # Converter created_at para o timezone e pegar a data
        if timezone.is_aware(attachment.created_at):
            attachment_day = timezone.localtime(attachment.created_at, tzinfo).date()
        else:
            attachment_day = attachment.created_at.date()
        
        if attachment_day in metrics_by_day:
            duration_ms = _extract_duration_ms_from_attachment(attachment)
            metrics_by_day[attachment_day]["duration_ms_total"] += duration_ms

    daily = []
    totals = {
        "minutes_total": Decimal("0.00"),
        "audio_count": 0,
        "success_count": 0,
        "failed_count": 0,
    }

    day_cursor = start_date
    while day_cursor <= end_date:
        row = metrics_by_day.get(day_cursor) or {}
        success_count = int(row.get("success_count") or 0)
        failed_count = int(row.get("failed_count") or 0)
        audio_count = success_count + failed_count
        duration_ms_total = int(row.get("duration_ms_total") or 0)
        minutes_total = (Decimal(duration_ms_total) / MINUTES_DIVISOR).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        daily.append(
            {
                "date": day_cursor,
                "minutes_total": float(minutes_total),
                "audio_count": audio_count,
                "success_count": success_count,
                "failed_count": failed_count,
            }
        )

        totals["minutes_total"] += minutes_total
        totals["audio_count"] += audio_count
        totals["success_count"] += success_count
        totals["failed_count"] += failed_count

        day_cursor += timedelta(days=1)

    totals["minutes_total"] = float(
        totals["minutes_total"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return daily, totals


def rebuild_transcription_metrics(tenant, start_date, end_date):
    start_datetime = timezone.make_aware(datetime.combine(start_date, dt_time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, dt_time.max))
    queryset = build_transcription_queryset(
        tenant,
        created_from=start_datetime,
        created_to=end_datetime,
    )
    daily, totals = aggregate_transcription_metrics(
        queryset,
        start_date=start_date,
        end_date=end_date,
    )

    for entry in daily:
        AiTranscriptionDailyMetric.objects.update_or_create(
            tenant=tenant,
            date=entry["date"],
            defaults={
                "minutes_total": entry["minutes_total"],
                "audio_count": entry["audio_count"],
                "success_count": entry["success_count"],
                "failed_count": entry["failed_count"],
            },
        )

    return daily, totals
