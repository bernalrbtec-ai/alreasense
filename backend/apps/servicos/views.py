"""
Views para a API de serviços (Redis overview, limpeza, histórico).
Acesso restrito a superadmin.
"""
import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import redis
from redis.exceptions import ResponseError
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PostgresOverviewSample, RedisCleanupLog, RedisUsageSample
from .redis_cleanup import SCAN_COUNT, _get_cache_key_prefix, _get_client, run_redis_cleanup

logger = logging.getLogger(__name__)

# Limite em segundos entre duas limpezas manuais pelo mesmo usuário
REDIS_CLEANUP_RATE_LIMIT_SECONDS = 30
# Logs "running" mais antigos que este valor (minutos) são marcados como failed
STALE_RUNNING_LOGS_MINUTES = 15
# Mínimo de segundos entre dois pedidos de persist-rewrite (disco) por usuário
REDIS_PERSIST_REWRITE_RATE_LIMIT_SECONDS = 60
# Intervalo mínimo (segundos) entre duas amostras de uso Redis para o gráfico
REDIS_USAGE_SAMPLE_INTERVAL_SECONDS = 600  # 10 min
# Quantos dias de amostras manter no banco (Redis)
REDIS_USAGE_SAMPLE_RETENTION_DAYS = 7
# Retenção das amostras de conexões/tamanho PostgreSQL (90 dias)
POSTGRES_USAGE_SAMPLE_RETENTION_DAYS = 90


def mark_stale_redis_cleanup_logs(minutes: int = STALE_RUNNING_LOGS_MINUTES) -> int:
    """
    Marca registros com status='running' e started_at anterior a `minutes` minutos
    como 'failed' com error_message indicando timeout. Retorna quantidade atualizada.
    """
    from django.utils import timezone
    threshold = timezone.now() - timezone.timedelta(minutes=minutes)
    updated = RedisCleanupLog.objects.filter(
        status="running",
        started_at__lt=threshold,
    ).update(
        status="failed",
        error_message="Timeout ou processo interrompido (log considerado travado).",
    )
    if updated:
        logger.info("Marcados %s log(s) Redis cleanup como failed (stale running).", updated)
    return updated


def _is_superadmin(request) -> bool:
    if not request.user or not request.user.is_authenticated:
        return False
    return bool(request.user.is_superuser or request.user.is_staff)


def _mask_broker_url(url: str) -> str:
    """Mascara senha em redis://, amqp://, etc., para exibição no admin."""
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        p = urlparse(raw)
        if not p.scheme:
            return "[URL sem esquema]"
        host = p.hostname or ""
        port_part = ""
        if p.port:
            port_part = f":{p.port}"
        user = p.username or ""
        if p.password:
            netloc = f"{user}:***@{host}{port_part}" if user else f"***@{host}{port_part}"
        else:
            netloc = p.netloc
        return urlunparse((p.scheme, netloc, p.path or "", p.params, p.query, p.fragment))
    except Exception:
        return "[URL inválida]"


def _celery_broker_transport_label(broker_url: str) -> str:
    scheme = (urlparse((broker_url or "").strip()).scheme or "").lower()
    if scheme in ("redis", "rediss"):
        return "redis"
    if scheme in ("amqp", "pyamqp"):
        return "amqp"
    if scheme == "sqs":
        return "sqs"
    return scheme or "unknown"


def _celery_broker_ping(broker_url: str) -> Tuple[bool, Optional[str]]:
    if not (broker_url or "").strip():
        return False, "CELERY_BROKER_URL vazia"
    try:
        from kombu import Connection

        with Connection(broker_url.strip(), connect_timeout=5) as conn:
            conn.ensure_connection(max_retries=1)
        return True, None
    except Exception as e:
        return False, str(e)[:220]


def _celery_workers_online_count() -> Tuple[Optional[int], Optional[str]]:
    """
    Retorna quantidade de workers que responderam ao ping.
    None = não foi possível determinar (erro de rede/Celery).
    """
    try:
        from alrea_sense.celery import app as celery_app

        insp = celery_app.control.inspect(timeout=2.0)
        if insp is None:
            return None, "inspect não inicializado"
        ping = insp.ping()
        if ping is None:
            return 0, None
        return len(ping), None
    except Exception as e:
        return None, str(e)[:220]


def _overview_celery_info() -> dict[str, Any]:
    broker_url = (getattr(settings, "CELERY_BROKER_URL", None) or "").strip()
    default_queue = (getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", None) or "celery").strip() or "celery"
    always_eager = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))
    transport = _celery_broker_transport_label(broker_url)

    warnings: list[str] = []
    if always_eager:
        warnings.append(
            "CELERY_TASK_ALWAYS_EAGER=true — tarefas executam no processo web (sem fila real). Desligue em produção."
        )
    if not broker_url:
        warnings.append("Defina CELERY_BROKER_URL (ou RABBITMQ_URL como fallback no settings).")

    broker_ok, broker_err = (False, None)
    if broker_url and not always_eager:
        broker_ok, broker_err = _celery_broker_ping(broker_url)
        if not broker_ok and broker_err:
            warnings.append(f"Broker inacessível a partir da API: {broker_err}")

    workers_count: Optional[int] = None
    workers_err: Optional[str] = None
    if broker_url and not always_eager:
        workers_count, workers_err = _celery_workers_online_count()
        if workers_err:
            warnings.append(f"Workers: {workers_err}")
        elif workers_count == 0:
            warnings.append(
                "Nenhum worker Celery respondeu ao ping. Suba um processo: "
                f"celery -A alrea_sense worker -l info -Q {default_queue}"
            )

    celery_queue_depth: Optional[Dict[str, Any]] = None
    if broker_ok and transport == "amqp" and default_queue:
        try:
            import pika

            params = pika.URLParameters(broker_url)
            params.socket_timeout = 5
            params.blocked_connection_timeout = 5
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            result = ch.queue_declare(queue=default_queue, passive=True)
            frame = getattr(result, "method", result) if result else None
            celery_queue_depth = {
                "queue": default_queue,
                "messages_ready": getattr(frame, "message_count", 0) if frame else 0,
                "consumers": getattr(frame, "consumer_count", 0) if frame else 0,
            }
            conn.close()
        except Exception as e:
            err = str(e)
            if "NOT_FOUND" in err or "404" in err:
                celery_queue_depth = {
                    "queue": default_queue,
                    "messages_ready": None,
                    "consumers": None,
                    "note": "Fila ainda não criada (normal se nunca houve task).",
                }
            else:
                celery_queue_depth = {"queue": default_queue, "error": err[:200]}

    return {
        "config_ok": bool(broker_url),
        "overview_api_path": "/api/servicos/celery/overview/",
        "broker_url_masked": _mask_broker_url(broker_url),
        "broker_transport": transport,
        "default_queue": default_queue,
        "task_always_eager": always_eager,
        "broker_reachable": broker_ok,
        "broker_error": broker_err,
        "workers_online": workers_count,
        "workers_error": workers_err,
        "worker_start_command": f"celery -A alrea_sense worker -l info -Q {default_queue}",
        "dify_debounce_task": "ai.run_dify_incoming_debounce_batch",
        "celery_queue": celery_queue_depth,
        "warnings": warnings,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def celery_overview(request):
    """Overview Celery: broker mascarado, fila, ping ao broker e aos workers (superadmin)."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response(_overview_celery_info())


def _overview_redis_info() -> dict[str, Any]:
    """Obtém INFO e contagens do Redis. Retorna dict com config_ok, error, used_memory, keys_*, etc."""
    red = getattr(settings, "REDIS_URL", "") or ""
    if not red:
        return {
            "config_ok": False,
            "error": "Redis não configurado",
            "used_memory": None,
            "used_memory_human": None,
            "keys_total": None,
            "keys_profile_pic": None,
            "keys_webhook": None,
            "warnings": [],
            "persistence": None,
        }

    try:
        client = redis.Redis.from_url(
            red,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        client.ping()
        info = client.info("memory")
        used_memory = info.get("used_memory")
        used_memory_human = info.get("used_memory_human", "0B")
        info_persist = client.info("persistence") or {}
        aof_enabled = bool(info_persist.get("aof_enabled"))
        aof_current_size = info_persist.get("aof_current_size") if aof_enabled else None
        rdb_last_save_time = info_persist.get("rdb_last_save_time")
        client.close()
    except Exception as e:
        logger.warning("Redis overview connection: %s", e)
        return {
            "config_ok": False,
            "error": f"Redis indisponível: {str(e)[:200]}",
            "used_memory": None,
            "used_memory_human": None,
            "keys_total": None,
            "keys_profile_pic": None,
            "keys_webhook": None,
            "warnings": [],
            "persistence": None,
        }

    warnings = []
    keys_total = None
    keys_profile_pic = None
    keys_webhook = None

    try:
        client = redis.Redis.from_url(
            red,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        info_keyspace = client.info("keyspace") or {}
        keys_total = 0
        for v in info_keyspace.values():
            # Formato pode ser string "keys=5,expires=0" ou dict {"keys": 5, "expires": 0}
            if isinstance(v, dict):
                try:
                    keys_total += int(v.get("keys", 0) or 0)
                except (ValueError, TypeError):
                    pass
            else:
                # Formato Redis: "keys=12995,expires=0" -> part = "keys=12995", parts = ["keys", "12995"]
                part = (v or "").split(",", 1)[0]
                if "=" in part:
                    parts = part.split("=")
                    if len(parts) >= 2 and parts[0] == "keys":
                        try:
                            keys_total += int(parts[1])
                        except (ValueError, TypeError):
                            pass
        client.close()
    except Exception as e:
        warnings.append(f"Contagem total de keys: {e}")

    prefix = _get_cache_key_prefix()
    pattern_pic = f"{prefix}:profile_pic:*"
    for db, pattern, key_out in [(2, pattern_pic, "keys_profile_pic"), (0, "webhook:*", "keys_webhook")]:
        try:
            c = _get_client(db)
            if not c:
                continue
            n = 0
            cursor = 0
            while True:
                cursor, keys = c.scan(cursor=cursor, match=pattern, count=SCAN_COUNT)
                n += len(keys)
                if cursor == 0:
                    break
            if key_out == "keys_profile_pic":
                keys_profile_pic = n
            else:
                keys_webhook = n
            c.close()
        except Exception as e:
            warnings.append(f"Contagem {key_out}: {e}")

    return {
        "config_ok": True,
        "error": None,
        "used_memory": used_memory,
        "used_memory_human": used_memory_human,
        "keys_total": keys_total,
        "keys_profile_pic": keys_profile_pic,
        "keys_webhook": keys_webhook,
        "warnings": warnings,
        "persistence": {
            "aof_enabled": aof_enabled,
            "aof_current_size": aof_current_size,
            "rdb_last_save_time": rdb_last_save_time,
        },
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def redis_overview(request):
    """Overview: config_ok, memória, keys, última limpeza, projeção de crescimento."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = _overview_redis_info()
    if data.get("config_ok") and data.get("used_memory") is not None:
        try:
            last_sample = RedisUsageSample.objects.order_by("-sampled_at").first()
            now = timezone.now()
            if last_sample is None or (now - last_sample.sampled_at).total_seconds() >= REDIS_USAGE_SAMPLE_INTERVAL_SECONDS:
                RedisUsageSample.objects.create(
                    used_memory=data["used_memory"],
                    aof_current_size=data.get("persistence") and data["persistence"].get("aof_current_size"),
                    keys_profile_pic=data.get("keys_profile_pic"),
                    keys_webhook=data.get("keys_webhook"),
                )
            cutoff = now - timezone.timedelta(days=REDIS_USAGE_SAMPLE_RETENTION_DAYS)
            try:
                RedisUsageSample.objects.filter(sampled_at__lt=cutoff).delete()
            except Exception as cleanup_err:
                logger.warning("Redis usage sample cleanup (retention): %s", cleanup_err)
            samples = list(
                RedisUsageSample.objects.filter(sampled_at__gte=cutoff).order_by("sampled_at")[:1008]
            )
            data["usage_history"] = [
                {
                    "sampled_at": s.sampled_at.isoformat(),
                    "used_memory": s.used_memory,
                    "aof_current_size": s.aof_current_size,
                    "keys_profile_pic": s.keys_profile_pic,
                    "keys_webhook": s.keys_webhook,
                }
                for s in samples
            ]
        except Exception as e:
            logger.warning("Redis usage history: %s", e)
            data["usage_history"] = []
    else:
        data["usage_history"] = []
    last = RedisCleanupLog.objects.exclude(status="running").order_by("-started_at").first()
    if last:
        data["last_cleanup"] = {
            "started_at": last.started_at.isoformat(),
            "finished_at": last.finished_at.isoformat() if last.finished_at else None,
            "status": last.status,
            "keys_deleted_profile_pic": last.keys_deleted_profile_pic,
            "keys_deleted_webhook": last.keys_deleted_webhook,
            "bytes_freed_estimate": last.bytes_freed_estimate,
            "duration_seconds": getattr(last, "duration_seconds", None),
        }
    else:
        data["last_cleanup"] = None

    # Projeção: média de keys removidas por limpeza nos últimos 30 dias (precisa >=2)
    from django.db.models import Avg

    recent = (
        RedisCleanupLog.objects.filter(status="success", started_at__gte=timezone.now() - timezone.timedelta(days=30))
        .order_by("-started_at")[:30]
    )
    recent = list(recent)
    if len(recent) >= 2:
        total_keys = sum(
            (r.keys_deleted_profile_pic or 0) + (r.keys_deleted_webhook or 0) for r in recent
        )
        avg_per_run = total_keys / len(recent)
        data["growth_projection"] = {
            "keys_per_day_estimate": int(avg_per_run),
            "message": f"~{int(avg_per_run)} keys removidas por limpeza (média últimos 30 dias)",
        }
    else:
        data["growth_projection"] = None

    return Response(data)


def _redis_stats_for_period(qs):
    from django.db.models import Avg, Sum
    total = qs.count()
    success = qs.filter(status="success").count()
    agg = qs.aggregate(
        pic=Sum("keys_deleted_profile_pic"),
        wh=Sum("keys_deleted_webhook"),
        bytes_=Sum("bytes_freed_estimate"),
        avg_duration=Avg("duration_seconds"),
    )
    tk = (agg["pic"] or 0) + (agg["wh"] or 0)
    tb = agg["bytes_"] or 0
    return {
        "total_cleanups": total,
        "success_count": success,
        "success_rate": (success / total * 100) if total else 0,
        "total_keys_deleted": tk,
        "total_bytes_freed_estimate": tb,
        "avg_duration_seconds": round(agg["avg_duration"] or 0, 2),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def redis_statistics(request):
    """Estatísticas agregadas de limpezas (7 e 30 dias)."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    last_7 = now - timezone.timedelta(days=7)
    last_30 = now - timezone.timedelta(days=30)
    from django.db.models import Avg, Sum

    qs_7 = RedisCleanupLog.objects.filter(started_at__gte=last_7).exclude(status="running")
    qs_30 = RedisCleanupLog.objects.filter(started_at__gte=last_30).exclude(status="running")
    stats_7 = _redis_stats_for_period(qs_7)
    stats_30 = _redis_stats_for_period(qs_30)

    success_qs = RedisCleanupLog.objects.filter(status="success")
    agg = success_qs.aggregate(
        pic=Avg("keys_deleted_profile_pic"),
        wh=Avg("keys_deleted_webhook"),
        bytes_=Avg("bytes_freed_estimate"),
    )
    avg_keys = (agg["pic"] or 0) + (agg["wh"] or 0)
    avg_bytes = agg["bytes_"] or 0

    return Response(
        {
            "last_7_days": stats_7,
            "last_30_days": stats_30,
            "avg_keys_deleted_per_run": round(avg_keys, 1),
            "avg_bytes_freed_per_run": round(avg_bytes, 1),
            "avg_duration_seconds": round(
                RedisCleanupLog.objects.filter(status="success").aggregate(
                    avg=Avg("duration_seconds")
                )["avg"] or 0,
                2,
            ),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def redis_cleanup_history(request):
    """Histórico paginado de limpezas Redis."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        page = max(1, int(request.query_params.get("page", 1)))
        page_size = min(max(1, int(request.query_params.get("page_size", 10))), 100)
    except (TypeError, ValueError):
        page = 1
        page_size = 10
    offset = (page - 1) * page_size
    qs = RedisCleanupLog.objects.order_by("-started_at").select_related("created_by")
    total = qs.count()
    logs = list(qs[offset : offset + page_size])
    results = [
        {
            "id": log.id,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "status": log.status,
            "keys_deleted_profile_pic": log.keys_deleted_profile_pic,
            "keys_deleted_webhook": log.keys_deleted_webhook,
            "bytes_freed_estimate": log.bytes_freed_estimate,
            "duration_seconds": getattr(log, "duration_seconds", None),
            "triggered_by": log.triggered_by,
            "created_by_email": getattr(log.created_by, "email", None) if log.created_by else None,
            "error_message": log.error_message or None,
        }
        for log in logs
    ]
    return Response(
        {
            "results": results,
            "count": total,
            "page": page,
            "page_size": page_size,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def redis_metrics(request):
    """Métricas resumidas para monitoramento (últimas 24h)."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    from django.db.models import Avg
    since = timezone.now() - timezone.timedelta(hours=24)
    qs = RedisCleanupLog.objects.filter(started_at__gte=since).exclude(status="running")
    success_count = qs.filter(status="success").count()
    failed_count = qs.filter(status="failed").count()
    agg = qs.filter(status="success").aggregate(avg_duration=Avg("duration_seconds"))
    return Response(
        {
            "last_24h": {
                "success_count": success_count,
                "failed_count": failed_count,
                "total": success_count + failed_count,
                "avg_duration_seconds": round(agg["avg_duration"] or 0, 2),
            }
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def redis_cleanup(request):
    """Executa limpeza Redis (manual). Retorna 409 se já houver uma em execução."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not (getattr(settings, "REDIS_URL", "") or "").strip():
        return Response(
            {"error": "Redis não configurado."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    mark_stale_redis_cleanup_logs()
    if RedisCleanupLog.objects.filter(status="running").exists():
        return Response(
            {"error": "Limpeza já em andamento. Aguarde a conclusão."},
            status=status.HTTP_409_CONFLICT,
        )
    profile_pic = request.data.get("profile_pic", True)
    webhook = request.data.get("webhook", False)
    if isinstance(profile_pic, str):
        profile_pic = profile_pic in ("true", "1", "yes")
    if isinstance(webhook, str):
        webhook = webhook in ("true", "1", "yes")
    if not profile_pic and not webhook:
        return Response(
            {"error": "Selecione ao menos um tipo de limpeza (profile_pic ou webhook)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from django.core.cache import cache
    rate_key = f"redis_cleanup_rate_limit:{getattr(request.user, 'id', 0)}"
    if cache.get(rate_key):
        return Response(
            {"error": f"Aguarde {REDIS_CLEANUP_RATE_LIMIT_SECONDS} segundos entre limpezas."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    cache.set(rate_key, 1, timeout=REDIS_CLEANUP_RATE_LIMIT_SECONDS)
    log = RedisCleanupLog.objects.create(
        status="running",
        triggered_by="manual",
        created_by=request.user,
    )
    try:
        result = run_redis_cleanup(profile_pic=profile_pic, webhook=webhook)
        log.finished_at = timezone.now()
        log.status = "success"
        log.keys_deleted_profile_pic = result["keys_deleted_profile_pic"]
        log.keys_deleted_webhook = result["keys_deleted_webhook"]
        log.bytes_freed_estimate = result.get("bytes_freed_estimate")
        log.duration_seconds = (log.finished_at - log.started_at).total_seconds()
        log.save(update_fields=["finished_at", "status", "keys_deleted_profile_pic", "keys_deleted_webhook", "bytes_freed_estimate", "duration_seconds"])
        persist_rewrite = _redis_persist_rewrite_result()
    except Exception as e:
        log.finished_at = timezone.now()
        log.status = "failed"
        log.error_message = str(e)[:2000]
        log.duration_seconds = (log.finished_at - log.started_at).total_seconds()
        log.save(update_fields=["finished_at", "status", "error_message", "duration_seconds"])
        return Response(
            {"error": str(e)[:500], "log": {"id": log.id, "status": log.status}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            "id": log.id,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat(),
            "status": log.status,
            "keys_deleted_profile_pic": log.keys_deleted_profile_pic,
            "keys_deleted_webhook": log.keys_deleted_webhook,
            "bytes_freed_estimate": log.bytes_freed_estimate,
            "duration_seconds": getattr(log, "duration_seconds", None),
            "triggered_by": log.triggered_by,
            "created_by_email": getattr(log.created_by, "email", None) if log.created_by else None,
            "error_message": None,
            "persist_rewrite": persist_rewrite,
        }
    )


def _redis_persist_rewrite_result() -> dict[str, Any]:
    """
    Tenta executar BGSAVE e BGREWRITEAOF no Redis padrão.
    Retorna dict com bgsave, bgrewriteaof ("ok"|"disabled"|"error"), message.
    Persistência é por instância; usa REDIS_URL (DB 0).
    """
    red = (getattr(settings, "REDIS_URL", "") or "").strip()
    if not red:
        return {"bgsave": "error", "bgrewriteaof": "error", "message": "Redis não configurado."}

    result = {"bgsave": "ok", "bgrewriteaof": "ok", "message": ""}
    messages = []

    try:
        client = redis.Redis.from_url(
            red,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=30,
        )
        client.ping()
    except Exception as e:
        return {"bgsave": "error", "bgrewriteaof": "error", "message": f"Redis indisponível: {str(e)[:200]}"}

    try:
        try:
            client.bgsave()
            messages.append("BGSAVE iniciado.")
        except ResponseError as e:
            err = str(e).lower()
            if "disabled" in err or "not allowed" in err or "denied" in err:
                result["bgsave"] = "disabled"
                messages.append("BGSAVE desabilitado (comum em Redis gerenciado).")
            else:
                result["bgsave"] = "error"
                messages.append(f"BGSAVE: {str(e)[:150]}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            result["bgsave"] = "error"
            messages.append(f"BGSAVE: {str(e)[:150]}")

        try:
            client.bgrewriteaof()
            messages.append("BGREWRITEAOF iniciado.")
        except ResponseError as e:
            err = str(e).lower()
            if "disabled" in err or "not allowed" in err or "denied" in err or "no append only" in err:
                result["bgrewriteaof"] = "disabled"
                messages.append("BGREWRITEAOF desabilitado ou AOF não ativo.")
            else:
                result["bgrewriteaof"] = "error"
                messages.append(f"BGREWRITEAOF: {str(e)[:150]}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            result["bgrewriteaof"] = "error"
            messages.append(f"BGREWRITEAOF: {str(e)[:150]}")
    finally:
        client.close()

    result["message"] = " ".join(messages).strip() or "Nenhuma ação executada."
    return result


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def redis_persist_rewrite(request):
    """
    Solicita ao Redis reescrever persistência em disco (BGSAVE + BGREWRITEAOF).
    Pode reduzir uso de disco após limpeza de keys. Em Redis gerenciado os comandos podem estar desabilitados.
    """
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    from django.core.cache import cache
    rate_key = f"redis_persist_rewrite_rate_limit:{getattr(request.user, 'id', 0)}"
    if cache.get(rate_key):
        return Response(
            {"error": f"Aguarde {REDIS_PERSIST_REWRITE_RATE_LIMIT_SECONDS} segundos antes de tentar novamente."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    cache.set(rate_key, 1, timeout=REDIS_PERSIST_REWRITE_RATE_LIMIT_SECONDS)
    data = _redis_persist_rewrite_result()
    return Response(data)


# Filas RabbitMQ conhecidas (nome fixo) para overview
RABBITMQ_KNOWN_QUEUES = [
    "campaigns.dlq",
    "chat_process_incoming_media",
    "chat_process_uploaded_file",
    "billing.overdue",
    "billing.upcoming",
    "billing.notification",
]
# Filas opcionais: não listar como aviso quando não existirem (ex.: campaigns.dlq só existe com campanhas)
RABBITMQ_OPTIONAL_QUEUES = frozenset(["campaigns.dlq"])


def _overview_rabbitmq_info() -> dict[str, Any]:
    """Overview RabbitMQ: conexão, consumer, filas conhecidas (message_count, consumer_count)."""
    rabbitmq_url = (getattr(settings, "RABBITMQ_URL", None) or "").strip()
    if not rabbitmq_url:
        return {
            "config_ok": False,
            "error": "RABBITMQ_URL não configurada",
            "connection_ok": False,
            "consumer_running": False,
            "active_campaign_threads": 0,
            "queues": [],
            "warnings": [],
            "warnings_queues_not_found": [],
        }
    try:
        import pika
        params = pika.URLParameters(rabbitmq_url)
        params.socket_timeout = 5
        params.blocked_connection_timeout = 5
        conn = pika.BlockingConnection(params)
        channel = conn.channel()
    except Exception as e:
        logger.warning("RabbitMQ overview connection: %s", e)
        return {
            "config_ok": False,
            "error": str(e)[:200],
            "connection_ok": False,
            "consumer_running": False,
            "active_campaign_threads": 0,
            "queues": [],
            "warnings": [],
            "warnings_queues_not_found": [],
        }
    consumer_running = False
    active_threads = 0
    try:
        from apps.campaigns.rabbitmq_consumer import get_rabbitmq_consumer
        c = get_rabbitmq_consumer()
        if c:
            consumer_running = getattr(c, "running", False)
            active_threads = len(getattr(c, "consumer_threads", {}) or {})
    except Exception:
        pass
    queues = []
    queues_not_found: list[str] = []
    for qname in RABBITMQ_KNOWN_QUEUES:
        try:
            result = channel.queue_declare(queue=qname, passive=True)
            frame = getattr(result, "method", result) if result else None
            if frame is None:
                queues.append({"name": qname, "messages_ready": 0, "consumers": 0})
                continue
            queues.append({
                "name": qname,
                "messages_ready": getattr(frame, "message_count", 0),
                "consumers": getattr(frame, "consumer_count", 0),
            })
        except Exception as e:
            err_str = str(e)
            is_not_found = "NOT_FOUND" in err_str or "no queue" in err_str.lower()
            if is_not_found and qname not in RABBITMQ_OPTIONAL_QUEUES:
                queues_not_found.append(qname)
            queues.append({"name": qname, "messages_ready": 0, "consumers": 0})
    try:
        conn.close()
    except Exception:
        pass
    warnings_summary: list[str] = []
    if queues_not_found:
        n = len(queues_not_found)
        names = ", ".join(queues_not_found)
        warnings_summary.append(f"{n} fila(s) não encontrada(s): {names}")
    return {
        "config_ok": True,
        "error": None,
        "connection_ok": True,
        "consumer_running": consumer_running,
        "active_campaign_threads": active_threads,
        "queues": queues,
        "warnings": warnings_summary,
        "warnings_queues_not_found": queues_not_found,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rabbitmq_overview(request):
    """Overview RabbitMQ: status, consumer, filas conhecidas."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response(_overview_rabbitmq_info())


def _overview_postgres_info() -> dict[str, Any]:
    """Overview PostgreSQL: conexões ativas, tamanho do banco, top tabelas."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as e:
        return {
            "config_ok": False,
            "error": str(e)[:200],
            "connection_count": None,
            "database_size_bytes": None,
            "database_size_human": None,
            "disk_total_bytes": None,
            "disk_free_bytes": None,
            "top_tables": [],
            "warnings": [],
        }
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            row = cursor.fetchone()
            connection_count = row[0] if row is not None else None
    except Exception as e:
        connection_count = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            row = cursor.fetchone()
            database_size_bytes = row[0] if row is not None else None
    except Exception as e:
        database_size_bytes = None
    if database_size_bytes is not None:
        if database_size_bytes >= 1024 ** 3:
            database_size_human = f"{database_size_bytes / 1024 ** 3:.2f} GB"
        elif database_size_bytes >= 1024 ** 2:
            database_size_human = f"{database_size_bytes / 1024 ** 2:.2f} MB"
        elif database_size_bytes >= 1024:
            database_size_human = f"{database_size_bytes / 1024:.2f} KB"
        else:
            database_size_human = f"{database_size_bytes} B"
    else:
        database_size_human = None
    top_tables = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT n.nspname || '.' || c.relname AS name,
                       pg_total_relation_size(c.oid) AS size_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_total_relation_size(c.oid) DESC
                LIMIT 10
            """)
            for row in cursor.fetchall():
                top_tables.append({"name": row[0], "size_bytes": row[1]})
    except Exception as e:
        pass
    disk_total_bytes = None
    disk_free_bytes = None
    try:
        import shutil
        with connection.cursor() as cursor:
            cursor.execute("SHOW data_directory")
            row = cursor.fetchone()
            if row and row[0]:
                usage = shutil.disk_usage(row[0])
                disk_total_bytes = usage.total
                disk_free_bytes = usage.free
    except Exception:
        pass
    return {
        "config_ok": True,
        "error": None,
        "connection_count": connection_count,
        "database_size_bytes": database_size_bytes,
        "database_size_human": database_size_human,
        "disk_total_bytes": disk_total_bytes,
        "disk_free_bytes": disk_free_bytes,
        "top_tables": top_tables,
        "warnings": [],
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def postgres_overview(request):
    """Overview PostgreSQL: conexões, tamanho do banco, maiores tabelas, histórico e pico 24h."""
    if not _is_superadmin(request):
        return Response(
            {"error": "Acesso negado. Apenas superadmin."},
            status=status.HTTP_403_FORBIDDEN,
        )
    data = _overview_postgres_info()
    # Amostras usam a tabela servicos_postgresoverview_sample (criada via scripts/sql/servicos_postgresoverview_sample.sql)
    if (
        data.get("config_ok")
        and data.get("connection_count") is not None
        and data.get("database_size_bytes") is not None
    ):
        try:
            last_sample = PostgresOverviewSample.objects.order_by("-sampled_at").first()
            now = timezone.now()
            if last_sample is None or (now - last_sample.sampled_at).total_seconds() >= REDIS_USAGE_SAMPLE_INTERVAL_SECONDS:
                PostgresOverviewSample.objects.create(
                    connection_count=data["connection_count"],
                    database_size_bytes=data["database_size_bytes"],
                )
            cutoff = now - timezone.timedelta(days=POSTGRES_USAGE_SAMPLE_RETENTION_DAYS)
            try:
                PostgresOverviewSample.objects.filter(sampled_at__lt=cutoff).delete()
            except Exception as cleanup_err:
                logger.warning("Postgres overview sample cleanup (retention): %s", cleanup_err)
            samples = list(
                PostgresOverviewSample.objects.filter(sampled_at__gte=cutoff).order_by("sampled_at")[:1008]
            )
            data["usage_history"] = [
                {
                    "sampled_at": s.sampled_at.isoformat(),
                    "connection_count": s.connection_count,
                    "database_size_bytes": s.database_size_bytes,
                }
                for s in samples
            ]
            if samples:
                last_24h = now - timezone.timedelta(hours=24)
                recent = [s for s in samples if s.sampled_at >= last_24h]
                if recent:
                    data["peak_24h_connections"] = max(s.connection_count for s in recent)
                    data["peak_24h_size_bytes"] = max(s.database_size_bytes for s in recent)
                else:
                    data["peak_24h_connections"] = max(s.connection_count for s in samples)
                    data["peak_24h_size_bytes"] = max(s.database_size_bytes for s in samples)
            else:
                data["peak_24h_connections"] = None
                data["peak_24h_size_bytes"] = None
        except Exception as e:
            logger.warning("Postgres usage history: %s", e)
            data["usage_history"] = []
            data["peak_24h_connections"] = None
            data["peak_24h_size_bytes"] = None
    else:
        data["usage_history"] = []
        data["peak_24h_connections"] = None
        data["peak_24h_size_bytes"] = None
    return Response(data)