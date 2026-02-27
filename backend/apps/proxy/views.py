"""
Views para a API de rotação de proxies.
Acesso restrito a superadmin (exceto rotação via API key).
"""
import logging

from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import ProxyRotationInstanceLog, ProxyRotationLog
from .serializers import ProxyRotationInstanceLogSerializer, ProxyRotationLogSerializer
from .services import _validate_proxy_api_key, run_proxy_rotation

logger = logging.getLogger(__name__)


def _is_superadmin(request) -> bool:
    """Verifica se o usuário é superadmin (is_superuser ou is_staff)."""
    if not request.user or not request.user.is_authenticated:
        return False
    return bool(request.user.is_superuser or request.user.is_staff)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proxy_overview(request):
    """Overview: config_ok, última execução, erros, warnings, is_running."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )

    webshare_key = getattr(settings, "WEBSHARE_API_KEY", "") or ""
    evolution_url = getattr(settings, "EVOLUTION_API_URL", "") or getattr(
        settings, "EVO_BASE_URL", ""
    )
    evolution_key = getattr(settings, "EVOLUTION_API_KEY", "") or getattr(
        settings, "EVO_API_KEY", ""
    )

    config_ok = bool(
        webshare_key
        and evolution_url
        and evolution_key
        and "SEU_" not in str(webshare_key)
        and "SEU_" not in str(evolution_key)
    )

    is_running = ProxyRotationLog.objects.filter(status="running").exists()

    last_log = ProxyRotationLog.objects.exclude(status="running").order_by("-created_at").first()
    last_execution = None
    last_errors = []
    warnings = []

    if last_log:
        last_execution = {
            "started_at": last_log.started_at,
            "finished_at": last_log.finished_at,
            "status": last_log.status,
            "num_proxies": last_log.num_proxies,
            "num_instances": last_log.num_instances,
            "num_updated": last_log.num_updated,
            "num_errors": last_log.num_instances - last_log.num_updated,
        }
        last_errors = list(
            ProxyRotationInstanceLog.objects.filter(
                rotation_log=last_log, success=False
            )
            .values_list("error_message", flat=True)[:5]
        )
        last_errors = [e for e in last_errors if e]
        if last_log.num_instances > last_log.num_proxies:
            warnings.append("Mais instâncias que proxies na última execução")

    return Response({
        "config_ok": config_ok,
        "last_execution": last_execution,
        "last_errors": last_errors,
        "is_running": is_running,
        "warnings": warnings,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def proxy_rotate(request):
    """Executa rotação. Aceita API key ou JWT + superadmin."""
    triggered_by = "manual"
    user = None

    # 1) Tentar API key
    api_ok, api_err = _validate_proxy_api_key(request)
    if api_ok:
        triggered_by = request.data.get("triggered_by", "scheduled")
        if triggered_by not in ("manual", "n8n", "scheduled"):
            triggered_by = "scheduled"
        user = None
    else:
        # 2) Tentar JWT + superadmin
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": api_err or "Autenticação necessária."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not _is_superadmin(request):
            return Response(
                {"error": "Acesso negado. Apenas superadmin."},
                status=status.HTTP_403_FORBIDDEN,
            )
        triggered_by = "manual"
        user = request.user

    log, err = run_proxy_rotation(triggered_by=triggered_by, user=user)
    if err and not log:
        return Response(
            {"error": err},
            status=status.HTTP_409_CONFLICT if "em execução" in err else status.HTTP_400_BAD_REQUEST,
        )
    # Falha com log criado (ex.: credenciais ausentes) — retorna 400 para o cliente exibir o erro
    if err and log and log.status == "failed":
        serializer = ProxyRotationLogSerializer(log)
        return Response(
            {"error": err, "log": serializer.data},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ProxyRotationLogSerializer(log)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proxy_rotation_history(request):
    """Histórico paginado de rotações."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )

    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 20)), 100)
    offset = (page - 1) * page_size

    queryset = ProxyRotationLog.objects.order_by("-created_at").select_related("created_by")
    total = queryset.count()
    logs = queryset[offset : offset + page_size]
    serializer = ProxyRotationLogSerializer(logs, many=True)

    return Response({
        "results": serializer.data,
        "count": total,
        "page": page,
        "page_size": page_size,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proxy_statistics(request):
    """Estatísticas agregadas."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    last_7 = now - timezone.timedelta(days=7)
    last_30 = now - timezone.timedelta(days=30)

    logs_7 = ProxyRotationLog.objects.filter(
        created_at__gte=last_7
    ).exclude(status="running")
    logs_30 = ProxyRotationLog.objects.filter(
        created_at__gte=last_30
    ).exclude(status="running")

    total_7 = logs_7.count()
    success_7 = logs_7.filter(status="success").count()
    total_30 = logs_30.count()
    success_30 = logs_30.filter(status="success").count()

    avg_updated = logs_30.aggregate(avg=Avg("num_updated"))["avg"] or 0

    return Response({
        "last_7_days": {
            "total": total_7,
            "success": success_7,
            "success_rate": (success_7 / total_7 * 100) if total_7 else 0,
        },
        "last_30_days": {
            "total": total_30,
            "success": success_30,
            "success_rate": (success_30 / total_30 * 100) if total_30 else 0,
        },
        "avg_updated_per_run": round(avg_updated, 1),
    })
