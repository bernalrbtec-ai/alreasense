"""
Agregação de métricas diárias de mensagens para relatórios.
Usado pelo job periódico e pela API (delta do dia incompleto).
"""
from datetime import timedelta, datetime, time
from collections import defaultdict
from itertools import groupby
from django.db.models import Count, Min
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.chat.models import Message


def aggregate_message_metrics_for_date(conversation_queryset, target_date):
    """
    Agrega métricas de mensagens para um conjunto de conversas em um único dia.

    Regras: is_internal=False, is_deleted=False.
    Retorna dict com: total_count, sent_count, received_count, series_by_hour,
    avg_first_response_seconds, by_user.
    """
    if hasattr(target_date, 'replace'):
        start_naive = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_naive = datetime.combine(target_date, time.min)
    start = timezone.make_aware(start_naive) if timezone.is_naive(start_naive) else start_naive
    end = start + timedelta(days=1)

    base_qs = Message.objects.filter(
        conversation__in=conversation_queryset,
        created_at__gte=start,
        created_at__lt=end,
        is_internal=False,
        is_deleted=False,
    )

    # Totais
    total_count = base_qs.count()
    sent_count = base_qs.filter(direction='outgoing').count()
    received_count = base_qs.filter(direction='incoming').count()

    # Por hora (0-23)
    hour_counts = (
        base_qs.annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(count=Count('id'))
    )
    series_by_hour = {str(h): 0 for h in range(24)}
    for row in hour_counts:
        series_by_hour[str(int(row['hour']))] = row['count']
    # Formato array para frontend: [ { hour: 0, total: n }, ... ]
    series_by_hour_list = [
        {'hour': h, 'total': series_by_hour[str(h)], 'sent': 0, 'received': 0}
        for h in range(24)
    ]
    hour_sent = (
        base_qs.filter(direction='outgoing')
        .annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(count=Count('id'))
    )
    hour_received = (
        base_qs.filter(direction='incoming')
        .annotate(hour=ExtractHour('created_at'))
        .values('hour')
        .annotate(count=Count('id'))
    )
    for row in hour_sent:
        h = int(row['hour'])
        series_by_hour_list[h]['sent'] = row['count']
    for row in hour_received:
        h = int(row['hour'])
        series_by_hour_list[h]['received'] = row['count']

    # Tempo médio de primeira resposta (por conversa: primeira incoming -> primeira outgoing)
    first_incoming = (
        base_qs.filter(direction='incoming')
        .values('conversation_id')
        .annotate(first_ts=Min('created_at'))
    )
    first_outgoing = (
        base_qs.filter(direction='outgoing')
        .values('conversation_id')
        .annotate(first_ts=Min('created_at'))
    )
    inc_map = {r['conversation_id']: r['first_ts'] for r in first_incoming}
    out_map = {r['conversation_id']: r['first_ts'] for r in first_outgoing}
    deltas = []
    for cid, t_in in inc_map.items():
        if cid in out_map and out_map[cid] > t_in:
            delta = (out_map[cid] - t_in).total_seconds()
            deltas.append(delta)
    avg_first_response_seconds = sum(deltas) / len(deltas) if deltas else None

    # Por usuário (outgoing): total_sent e opcionalmente avg_first_response quando foi o primeiro a responder
    by_user_raw = (
        base_qs.filter(direction='outgoing', sender_id__isnull=False)
        .values('sender_id')
        .annotate(total_sent=Count('id'))
    )
    by_user = {}
    for row in by_user_raw:
        uid = str(row['sender_id'])
        by_user[uid] = {'total_sent': row['total_sent'], 'avg_first_response_seconds': None}
    # avg_first_response por usuário (quando esse usuário enviou a primeira outgoing da conversa)
    first_outgoing_per_conv = (
        base_qs.filter(direction='outgoing', sender_id__isnull=False)
        .values('conversation_id', 'sender_id', 'created_at')
        .order_by('conversation_id', 'created_at')
    )
    first_sender_per_conv = {}
    for conv_id, rows in groupby(
        first_outgoing_per_conv, key=lambda x: x['conversation_id']
    ):
        first = next(rows)
        first_sender_per_conv[conv_id] = (first['sender_id'], first['created_at'])
    user_deltas = defaultdict(list)
    for cid, t_in in inc_map.items():
        if cid not in first_sender_per_conv:
            continue
        sender_id, t_out = first_sender_per_conv[cid]
        if t_out > t_in:
            user_deltas[str(sender_id)].append((t_out - t_in).total_seconds())
    for uid in by_user:
        if uid in user_deltas and user_deltas[uid]:
            by_user[uid]['avg_first_response_seconds'] = sum(user_deltas[uid]) / len(user_deltas[uid])

    return {
        'total_count': total_count,
        'sent_count': sent_count,
        'received_count': received_count,
        'series_by_hour': series_by_hour_list,
        'avg_first_response_seconds': avg_first_response_seconds,
        'by_user': by_user,
    }
