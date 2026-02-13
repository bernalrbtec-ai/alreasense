"""
Endpoint de métricas de mensagens para relatórios (API híbrida).
Lê dias persistidos em ChatMessageDailyMetric e agrega o dia incompleto em tempo real.
"""
import logging
from datetime import datetime, date, timedelta, time
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate, ExtractHour
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.chat.models import Conversation, ChatMessageDailyMetric, Message
from apps.chat.message_metrics import aggregate_message_metrics_for_date

logger = logging.getLogger(__name__)


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _get_conversations_queryset(user, department_id=None, agent_id=None):
    """Queryset de conversas que o usuário pode ver (mesma lógica do ConversationViewSet)."""
    from django.db.models import Q
    base = Conversation.objects.filter(tenant=user.tenant)
    if user.is_admin:
        qs = base
    else:
        department_ids = list(user.departments.values_list("id", flat=True))
        if department_ids:
            qs = base.filter(
                Q(department__in=department_ids)
                | Q(assigned_to=user)
                | Q(department__isnull=True, status="pending")
            ).distinct()
        else:
            qs = base.filter(
                Q(assigned_to=user) | Q(department__isnull=True, status="pending")
            ).distinct()
    if department_id:
        qs = qs.filter(department_id=department_id)
    if agent_id:
        qs = qs.filter(assigned_to_id=agent_id)
    return qs


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def message_metrics(request):
    """
    GET /api/chat/metrics/messages/
    Params: created_from, created_to (YYYY-MM-DD), department_id, agent_id (opcional).
    Retorna: totals, series_by_hour, avg_first_response_seconds, by_user, range.
    """
    user = request.user
    if not user.tenant:
        return Response(
            {"error": "Tenant não associado."},
            status=400,
        )

    created_from = _parse_date(request.query_params.get("created_from"))
    created_to = _parse_date(request.query_params.get("created_to"))
    department_id = request.query_params.get("department_id") or None
    agent_id = request.query_params.get("agent_id") or None

    # Default: últimos 30 dias
    today = timezone.now().date()
    if not created_from:
        created_from = today - timedelta(days=30)
    if not created_to:
        created_to = today
    if created_from > created_to:
        created_from, created_to = created_to, created_from

    conv_qs = _get_conversations_queryset(user, department_id=department_id, agent_id=agent_id)

    # Acumuladores
    total_count = 0
    sent_count = 0
    received_count = 0
    series_by_hour = [{"hour": h, "total": 0, "sent": 0, "received": 0} for h in range(24)]
    series_by_date = []
    avg_sum = 0.0
    avg_weight = 0
    by_user = {}

    # Com filtro de departamento/agente não temos métricas pré-agregadas; calculamos tudo em tempo real.
    use_table = not (department_id or agent_id)
    current = created_from
    while current <= created_to:
        day_total = 0
        day_sent = 0
        day_received = 0
        if use_table and current < today:
            rows = ChatMessageDailyMetric.objects.filter(
                tenant=user.tenant,
                date=current,
                department__isnull=True,
            )
            for row in rows:
                total_count += row.total_count
                sent_count += row.sent_count
                received_count += row.received_count
                day_total += row.total_count
                day_sent += row.sent_count
                day_received += row.received_count
                sh = row.series_by_hour or []
                if isinstance(sh, list):
                    for item in sh:
                        h = item.get("hour", 0)
                        if 0 <= h < 24:
                            series_by_hour[h]["total"] += item.get("total", 0)
                            series_by_hour[h]["sent"] += item.get("sent", 0)
                            series_by_hour[h]["received"] += item.get("received", 0)
                if row.avg_first_response_seconds is not None and row.total_count:
                    avg_sum += row.avg_first_response_seconds * row.total_count
                    avg_weight += row.total_count
                for uid, ud in (row.by_user or {}).items():
                    if uid not in by_user:
                        by_user[uid] = {"total_sent": 0, "avg_first_response_seconds": None, "_resp_sum": 0.0, "_resp_n": 0}
                    by_user[uid]["total_sent"] += ud.get("total_sent", 0)
                    if ud.get("avg_first_response_seconds") is not None:
                        by_user[uid]["_resp_sum"] += ud["avg_first_response_seconds"] * ud.get("total_sent", 0)
                        by_user[uid]["_resp_n"] += ud.get("total_sent", 0)
            series_by_date.append({
                "date": current.isoformat(),
                "total": day_total,
                "sent": day_sent,
                "received": day_received,
            })
        else:
            # Dia incompleto (hoje) ou filtro department/agent: agregação em tempo real
            data = aggregate_message_metrics_for_date(conv_qs, current)
            total_count += data["total_count"]
            sent_count += data["sent_count"]
            received_count += data["received_count"]
            for item in data.get("series_by_hour") or []:
                h = item.get("hour", 0)
                if 0 <= h < 24:
                    series_by_hour[h]["total"] += item.get("total", 0)
                    series_by_hour[h]["sent"] += item.get("sent", 0)
                    series_by_hour[h]["received"] += item.get("received", 0)
            if data.get("avg_first_response_seconds") is not None and data["total_count"]:
                avg_sum += data["avg_first_response_seconds"] * data["total_count"]
                avg_weight += data["total_count"]
            for uid, ud in (data.get("by_user") or {}).items():
                if uid not in by_user:
                    by_user[uid] = {"total_sent": 0, "avg_first_response_seconds": None, "_resp_sum": 0.0, "_resp_n": 0}
                by_user[uid]["total_sent"] += ud.get("total_sent", 0)
                if ud.get("avg_first_response_seconds") is not None:
                    n = ud.get("total_sent", 0) or 1
                    by_user[uid]["_resp_sum"] += ud["avg_first_response_seconds"] * n
                    by_user[uid]["_resp_n"] += n
            series_by_date.append({
                "date": current.isoformat(),
                "total": data["total_count"],
                "sent": data["sent_count"],
                "received": data["received_count"],
            })
        current += timedelta(days=1)

    # Média ponderada global
    avg_first_response_seconds = (avg_sum / avg_weight) if avg_weight else None

    # Limpar by_user: remover _resp_* e calcular média ponderada por usuário
    from apps.authn.models import User
    user_ids = list(by_user.keys())
    users_map = {str(u.id): u for u in User.objects.filter(id__in=user_ids)} if user_ids else {}
    by_user_list = []
    for uid, ud in by_user.items():
        resp_n = ud.pop("_resp_n", 0)
        resp_sum = ud.pop("_resp_sum", 0.0)
        ud["avg_first_response_seconds"] = (resp_sum / resp_n) if resp_n else None
        u = users_map.get(uid)
        by_user_list.append({
            "user_id": uid,
            "email": getattr(u, "email", "") if u else "",
            "first_name": getattr(u, "first_name", "") if u else "",
            "last_name": getattr(u, "last_name", "") if u else "",
            "total_sent": ud["total_sent"],
            "avg_first_response_seconds": ud["avg_first_response_seconds"],
        })

    # by_department_user: departamento x usuário x mensagens x dia
    start_dt = timezone.make_aware(datetime.combine(created_from, time.min))
    end_dt = timezone.make_aware(datetime.combine(created_to + timedelta(days=1), time.min))
    dept_user_rows = (
        Message.objects.filter(
            conversation__in=conv_qs,
            created_at__gte=start_dt,
            created_at__lt=end_dt,
            is_internal=False,
            is_deleted=False,
            direction="outgoing",
            sender_id__isnull=False,
        )
        .annotate(msg_date=TruncDate("created_at"))
        .values("conversation__department_id", "conversation__department__name", "sender_id", "msg_date")
        .annotate(sent=Count("id"))
    )
    dept_user_map = {}  # (dept_id, user_id) -> { department_id, department_name, user_id, total_sent, by_date: [] }
    all_user_ids = set()
    for row in dept_user_rows:
        dept_id = str(row["conversation__department_id"]) if row["conversation__department_id"] else "_inbox"
        dept_name = row["conversation__department__name"] or "Inbox (sem departamento)"
        uid = str(row["sender_id"])
        msg_date = row["msg_date"].isoformat() if row["msg_date"] else None
        sent = row["sent"] or 0
        key = (dept_id, uid)
        if key not in dept_user_map:
            dept_user_map[key] = {
                "department_id": dept_id if dept_id != "_inbox" else None,
                "department_name": dept_name,
                "user_id": uid,
                "total_sent": 0,
                "by_date": [],
            }
        dept_user_map[key]["total_sent"] += sent
        if msg_date:
            dept_user_map[key]["by_date"].append({"date": msg_date, "sent": sent})
        all_user_ids.add(uid)
    dept_user_users = {str(u.id): u for u in User.objects.filter(id__in=all_user_ids)} if all_user_ids else {}
    by_department_user_list = []
    for (_, _), entry in dept_user_map.items():
        u = dept_user_users.get(entry["user_id"])
        user_name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip() or getattr(u, "email", "") or entry["user_id"][:8]
        entry["by_date"].sort(key=lambda x: x["date"])
        by_department_user_list.append({
            **entry,
            "user_name": user_name,
        })
    by_department_user_list.sort(key=lambda x: x["total_sent"], reverse=True)

    # series_by_hour_by_department: média de mensagens por hora do dia, por departamento
    num_days = max(1, (created_to - created_from).days + 1)
    dept_hour_rows = (
        Message.objects.filter(
            conversation__in=conv_qs,
            created_at__gte=start_dt,
            created_at__lt=end_dt,
            is_internal=False,
            is_deleted=False,
        )
        .annotate(hour=ExtractHour("created_at"))
        .values("conversation__department_id", "conversation__department__name", "hour")
        .annotate(total=Count("id"))
    )
    dept_hour_map = {}  # (dept_id,) -> { department_id, department_name, by_hour: { 0: n, 1: m, ... } }
    for row in dept_hour_rows:
        dept_id = str(row["conversation__department_id"]) if row["conversation__department_id"] else "_inbox"
        dept_name = row["conversation__department__name"] or "Inbox (sem departamento)"
        h = int(row["hour"]) if row["hour"] is not None else 0
        total = row["total"] or 0
        if dept_id not in dept_hour_map:
            dept_hour_map[dept_id] = {
                "department_id": dept_id if dept_id != "_inbox" else None,
                "department_name": dept_name,
                "by_hour": {hr: 0 for hr in range(24)},
            }
        dept_hour_map[dept_id]["by_hour"][h] = total
    series_by_hour_by_department = []
    for dept_id, entry in dept_hour_map.items():
        by_hour_list = [
            {"hour": h, "total": entry["by_hour"].get(h, 0), "avg": entry["by_hour"].get(h, 0) / num_days}
            for h in range(24)
        ]
        series_by_hour_by_department.append({
            "department_id": entry["department_id"],
            "department_name": entry["department_name"],
            "by_hour": by_hour_list,
        })

    return Response({
        "range": {
            "from": created_from.isoformat(),
            "to": created_to.isoformat(),
            "timezone": str(timezone.get_current_timezone()),
        },
        "totals": {
            "total": total_count,
            "sent": sent_count,
            "received": received_count,
        },
        "series_by_hour": series_by_hour,
        "series_by_date": series_by_date,
        "avg_first_response_seconds": avg_first_response_seconds,
        "by_user": by_user_list,
        "by_department_user": by_department_user_list,
        "series_by_hour_by_department": series_by_hour_by_department,
        "num_days": num_days,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTenantMember, IsAdminUser])
def message_metrics_rebuild(request):
    """
    POST /api/chat/metrics/messages/rebuild/
    Body: { "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" }
    Reagrega métricas do período e grava em ChatMessageDailyMetric (igual ao comando).
    """
    user = request.user
    if not user.tenant:
        return Response({"error": "Tenant não associado."}, status=status.HTTP_400_BAD_REQUEST)

    created_from = _parse_date(request.data.get("from"))
    created_to = _parse_date(request.data.get("to"))
    if not created_from or not created_to:
        return Response(
            {"error": "Informe 'from' e 'to' no body (YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if created_from > created_to:
        created_from, created_to = created_to, created_from

    conv_qs = Conversation.objects.filter(tenant=user.tenant)
    total_count = 0
    sent_count = 0
    received_count = 0
    days_processed = 0
    current = created_from
    while current <= created_to:
        data = aggregate_message_metrics_for_date(conv_qs, current)
        with transaction.atomic():
            ChatMessageDailyMetric.objects.update_or_create(
                tenant=user.tenant,
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

    return Response({
        "status": "success",
        "message": f"Métricas de mensagens atualizadas de {created_from} até {created_to}",
        "range": {"from": created_from.isoformat(), "to": created_to.isoformat()},
        "days_processed": days_processed,
        "totals": {"total": total_count, "sent": sent_count, "received": received_count},
    })
