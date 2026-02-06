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


def build_transcription_queryset(tenant, created_from, created_to, department_id=None, agent_id=None, use_select_related=True):
    """Constrói queryset de attachments de áudio.
    
    Args:
        use_select_related: Se False, não faz select_related (útil quando usar only() depois)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # ✅ CRÍTICO: Filtrar explicitamente por tenant_id para garantir isolamento
    queryset = MessageAttachment.objects.filter(
        tenant_id=tenant.id,  # Usar tenant_id explicitamente
        mime_type__startswith="audio/",
    )
    
    logger.debug(
        f"Building transcription queryset for tenant_id={tenant.id}, "
        f"created_from={created_from}, created_to={created_to}"
    )
    
    # Só fazer select_related se necessário e não vamos usar only() depois
    if use_select_related:
        queryset = queryset.select_related("message", "message__conversation")

    if created_from:
        queryset = queryset.filter(created_at__gte=created_from)
    if created_to:
        queryset = queryset.filter(created_at__lte=created_to)
    if department_id:
        queryset = queryset.filter(message__conversation__department_id=department_id)
    if agent_id:
        queryset = queryset.filter(message__conversation__assigned_to_id=agent_id)
    
    logger.debug(f"Final queryset count: {queryset.count()} attachments")
    return queryset


def _extract_duration_ms_from_attachment(attachment) -> int:
    """Extrai duration_ms de um attachment usando a mesma lógica do triage_service."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Tentar metadata primeiro
    if attachment.metadata:
        duration_ms = attachment.metadata.get('duration_ms')
        if duration_ms is not None:
            logger.debug(f"Found duration_ms in metadata: {duration_ms} for attachment {attachment.id}")
            return int(duration_ms)
        duration = attachment.metadata.get('duration')
        if duration is not None:
            logger.debug(f"Found duration in metadata: {duration} for attachment {attachment.id}")
            return int(float(duration) * 1000)
    
    # Tentar ai_metadata (pode estar no nível raiz ou aninhado)
    if attachment.ai_metadata:
        # Tentar nível raiz primeiro
        duration_ms = attachment.ai_metadata.get('duration_ms')
        if duration_ms is not None:
            logger.debug(f"Found duration_ms in ai_metadata root: {duration_ms} for attachment {attachment.id}")
            return int(duration_ms)
        duration = attachment.ai_metadata.get('duration')
        if duration is not None:
            logger.debug(f"Found duration in ai_metadata root: {duration} for attachment {attachment.id}")
            return int(float(duration) * 1000)
        
        # Tentar dentro de transcription (onde pode estar salvo)
        transcription_data = attachment.ai_metadata.get('transcription') or {}
        if isinstance(transcription_data, dict):
            duration_ms = transcription_data.get('duration_ms')
            if duration_ms is not None:
                logger.debug(f"Found duration_ms in ai_metadata.transcription: {duration_ms} for attachment {attachment.id}")
                return int(duration_ms)
            duration = transcription_data.get('duration')
            if duration is not None:
                logger.debug(f"Found duration in ai_metadata.transcription: {duration} for attachment {attachment.id}")
                return int(float(duration) * 1000)
    
    logger.warning(f"No duration found for attachment {attachment.id}. metadata={attachment.metadata}, ai_metadata={attachment.ai_metadata}")
    return 0


def _extract_latency_ms_from_attachment(attachment) -> int | None:
    """Extrai latency_ms (processing_time_ms) de um attachment."""
    if not attachment.ai_metadata:
        return None
    
    transcription_data = attachment.ai_metadata.get('transcription') or {}
    if isinstance(transcription_data, dict):
        processing_time_ms = transcription_data.get('processing_time_ms')
        if processing_time_ms is not None:
            return int(processing_time_ms)
    
    return None


def _extract_model_name_from_attachment(attachment) -> str | None:
    """Extrai model_name de um attachment."""
    if not attachment.ai_metadata:
        return None
    
    transcription_data = attachment.ai_metadata.get('transcription') or {}
    if isinstance(transcription_data, dict):
        model_name = transcription_data.get('model_name') or transcription_data.get('model')
        if model_name:
            return str(model_name)
    
    return None


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
            "quality_correct_count": 0,
            "quality_incorrect_count": 0,
            "quality_unrated_count": 0,
            "latency_ms_list": [],
            "models_used": {},
        }
    
    # Buscar todos os attachments com sucesso e calcular métricas em Python
    # Remover select_related antes de usar only() para evitar conflito
    success_attachments = queryset.filter(success_filter).select_related(None).only(
        'id', 'metadata', 'ai_metadata', 'created_at', 'transcription_quality'
    )
    
    for attachment in success_attachments:
        # Converter created_at para o timezone e pegar a data
        if timezone.is_aware(attachment.created_at):
            attachment_day = timezone.localtime(attachment.created_at, tzinfo).date()
        else:
            attachment_day = attachment.created_at.date()
        
        if attachment_day in metrics_by_day:
            day_metrics = metrics_by_day[attachment_day]
            
            # Duration
            duration_ms = _extract_duration_ms_from_attachment(attachment)
            day_metrics["duration_ms_total"] += duration_ms
            
            # Quality
            quality = attachment.transcription_quality
            if quality == 'correct':
                day_metrics["quality_correct_count"] += 1
            elif quality == 'incorrect':
                day_metrics["quality_incorrect_count"] += 1
            else:
                day_metrics["quality_unrated_count"] += 1
            
            # Latency
            latency_ms = _extract_latency_ms_from_attachment(attachment)
            if latency_ms is not None:
                day_metrics["latency_ms_list"].append(latency_ms)
            
            # Model
            model_name = _extract_model_name_from_attachment(attachment)
            if model_name:
                day_metrics["models_used"][model_name] = day_metrics["models_used"].get(model_name, 0) + 1

    daily = []
    totals = {
        "minutes_total": Decimal("0.00"),
        "audio_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "quality_correct_count": 0,
        "quality_incorrect_count": 0,
        "quality_unrated_count": 0,
        "latency_ms_list": [],
        "models_used": {},
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
        
        quality_correct = int(row.get("quality_correct_count") or 0)
        quality_incorrect = int(row.get("quality_incorrect_count") or 0)
        quality_unrated = int(row.get("quality_unrated_count") or 0)
        
        latency_ms_list = row.get("latency_ms_list") or []
        avg_latency_ms = None
        if latency_ms_list:
            avg_latency_ms = float(sum(latency_ms_list) / len(latency_ms_list))
        
        models_used = row.get("models_used") or {}

        daily.append(
            {
                "date": day_cursor,
                "minutes_total": float(minutes_total),
                "audio_count": audio_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "quality_correct_count": quality_correct,
                "quality_incorrect_count": quality_incorrect,
                "quality_unrated_count": quality_unrated,
                "avg_latency_ms": avg_latency_ms,
                "models_used": models_used,
            }
        )

        totals["minutes_total"] += minutes_total
        totals["audio_count"] += audio_count
        totals["success_count"] += success_count
        totals["failed_count"] += failed_count
        totals["quality_correct_count"] += quality_correct
        totals["quality_incorrect_count"] += quality_incorrect
        totals["quality_unrated_count"] += quality_unrated
        totals["latency_ms_list"].extend(latency_ms_list)
        
        # Agregar modelos
        for model_name, count in models_used.items():
            totals["models_used"][model_name] = totals["models_used"].get(model_name, 0) + count

        day_cursor += timedelta(days=1)

    totals["minutes_total"] = float(
        totals["minutes_total"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    
    # Calcular latência média geral
    totals["avg_latency_ms"] = None
    if totals["latency_ms_list"]:
        totals["avg_latency_ms"] = float(sum(totals["latency_ms_list"]) / len(totals["latency_ms_list"]))
    del totals["latency_ms_list"]  # Remover lista, manter apenas média
    
    return daily, totals


def rebuild_transcription_metrics(tenant, start_date, end_date):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(
        f"Rebuilding transcription metrics for tenant_id={tenant.id} "
        f"from {start_date} to {end_date}"
    )
    
    start_datetime = timezone.make_aware(datetime.combine(start_date, dt_time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, dt_time.max))
    queryset = build_transcription_queryset(
        tenant,
        created_from=start_datetime,
        created_to=end_datetime,
        use_select_related=False,  # Não precisa porque vamos usar defer() depois
    )
    daily, totals = aggregate_transcription_metrics(
        queryset,
        start_date=start_date,
        end_date=end_date,
    )

    logger.info(
        f"Rebuilt {len(daily)} daily metrics for tenant_id={tenant.id}. "
        f"Total: {totals['minutes_total']} minutes, {totals['audio_count']} audios"
    )

    for entry in daily:
        # ✅ CRÍTICO: Usar tenant_id explicitamente no update_or_create
        AiTranscriptionDailyMetric.objects.update_or_create(
            tenant_id=tenant.id,  # Usar tenant_id explicitamente
            date=entry["date"],
            defaults={
                "minutes_total": entry["minutes_total"],
                "audio_count": entry["audio_count"],
                "success_count": entry["success_count"],
                "failed_count": entry["failed_count"],
                "quality_correct_count": entry["quality_correct_count"],
                "quality_incorrect_count": entry["quality_incorrect_count"],
                "quality_unrated_count": entry["quality_unrated_count"],
                "avg_latency_ms": Decimal(str(entry["avg_latency_ms"])) if entry["avg_latency_ms"] is not None else None,
                "models_used": entry["models_used"],
            },
        )

    return daily, totals
