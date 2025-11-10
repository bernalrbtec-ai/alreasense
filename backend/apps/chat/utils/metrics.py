"""
Utilitários para armazenar métricas simples em cache (Redis).
Mantém estatísticas básicas de latência e erros para integrações externas.
"""
from __future__ import annotations

from typing import Any, Dict
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

METRICS_CACHE_KEY = "chat:metrics:evolution"
METRICS_CACHE_TIMEOUT = 60 * 60  # 1 hora
WORKERS_CACHE_KEY = "chat:metrics:workers"
WORKER_HEARTBEAT_TIMEOUT = 60  # segundos
WORKER_STALE_SECONDS = 45


def _load_metrics() -> Dict[str, Any]:
    return cache.get(METRICS_CACHE_KEY, {}).copy()


def _save_metrics(data: Dict[str, Any]) -> None:
    cache.set(METRICS_CACHE_KEY, data, timeout=METRICS_CACHE_TIMEOUT)


def record_latency(metric: str, latency_seconds: float, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Atualiza métricas de latência de forma incremental.
    """
    data = _load_metrics()
    entry = data.get(
        metric,
        {
            "count": 0,
            "avg_latency": 0.0,
            "min_latency": latency_seconds,
            "max_latency": latency_seconds,
        },
    )

    previous_count = int(entry.get("count", 0))
    new_count = previous_count + 1
    previous_avg = float(entry.get("avg_latency", 0.0))
    new_avg = ((previous_avg * previous_count) + latency_seconds) / new_count

    entry.update(
        {
            "count": new_count,
            "avg_latency": round(new_avg, 4),
            "min_latency": round(min(entry.get("min_latency", latency_seconds), latency_seconds), 4),
            "max_latency": round(max(entry.get("max_latency", latency_seconds), latency_seconds), 4),
            "last_latency": round(latency_seconds, 4),
            "last_updated": timezone.now().isoformat(),
        }
    )

    if extra:
        entry["extra"] = extra

    data[metric] = entry
    _save_metrics(data)
    return entry


def record_error(metric: str, message: str) -> Dict[str, Any]:
    """
    Registra a última mensagem de erro observada para um metric.
    """
    data = _load_metrics()
    entry = data.get(metric, {})
    entry.update(
        {
            "last_error": {
                "message": str(message),
                "timestamp": timezone.now().isoformat(),
            },
            "errors": entry.get("errors", 0) + 1,
            "last_updated": timezone.now().isoformat(),
        }
    )
    data[metric] = entry
    _save_metrics(data)
    return entry


def get_metrics() -> Dict[str, Any]:
    """
    Retorna snapshot das métricas armazenadas.
    """
    return _load_metrics()


def reset_metrics() -> None:
    """
    Limpa métricas (utilizado em testes).
    """
    cache.delete(METRICS_CACHE_KEY)


def update_worker_heartbeat(worker_type: str, worker_id: int | str) -> None:
    """
    Registra um heartbeat simples do worker (mantém vivo por 1 minuto).
    """
    workers = cache.get(WORKERS_CACHE_KEY, {}).copy()
    worker_dict = workers.get(worker_type, {})
    worker_dict[str(worker_id)] = timezone.now().isoformat()
    workers[worker_type] = worker_dict
    cache.set(WORKERS_CACHE_KEY, workers, timeout=WORKER_HEARTBEAT_TIMEOUT)


def get_worker_status() -> Dict[str, Any]:
    """
    Retorna informações de heartbeat dos workers (ativos x obsoletos).
    """
    workers = cache.get(WORKERS_CACHE_KEY, {})
    if not workers:
        return {}

    now = timezone.now()
    status: Dict[str, Any] = {}

    for worker_type, heartbeat_map in workers.items():
        active = 0
        details = []

        for worker_id, heartbeat in heartbeat_map.items():
            dt = parse_datetime(heartbeat)
            if dt is None:
                continue
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())

            age_seconds = (now - dt).total_seconds()
            is_active = age_seconds <= WORKER_STALE_SECONDS
            if is_active:
                active += 1

            details.append({
                "id": worker_id,
                "last_seen": heartbeat,
                "age_seconds": round(age_seconds, 2),
                "state": "active" if is_active else "stale",
            })

        status[worker_type] = {
            "active": active,
            "total": len(details),
            "workers": details,
            "stale_threshold_seconds": WORKER_STALE_SECONDS,
            "last_refreshed": now.isoformat(),
        }

    return status
