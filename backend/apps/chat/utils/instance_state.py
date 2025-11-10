"""
Helpers para armazenar e consultar o estado corrente das instâncias Evolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from django.core.cache import cache
from django.utils import timezone


CACHE_KEY = "chat:instance_state:{instance_name}"
STATE_TTL_SECONDS = 180  # 3 minutos
STALE_AFTER_SECONDS = 30  # Se não atualizar nesse período, considerar stale
MAX_BACKOFF_SECONDS = 30


@dataclass
class InstanceState:
    instance: str
    state: str = "unknown"
    status_reason: Optional[int] = None
    updated_at: float = timezone.now().timestamp()
    raw: Optional[dict] = None

    @property
    def age(self) -> float:
        return timezone.now().timestamp() - self.updated_at

    @property
    def is_open(self) -> bool:
        return (self.state or "").lower() in {"open", "connected"}

    @property
    def is_stale(self) -> bool:
        return self.age > STALE_AFTER_SECONDS


def _build_cache_key(instance_name: str) -> str:
    return CACHE_KEY.format(instance_name=instance_name)


def set_instance_state(instance_name: str, data: dict) -> None:
    """
    Armazena estado da instância no cache.
    """
    if not instance_name:
        return

    payload = {
        "instance": instance_name,
        "state": data.get("state") or data.get("connection_state") or "unknown",
        "status_reason": data.get("statusReason"),
        "updated_at": timezone.now().timestamp(),
        "raw": data,
    }

    cache.set(_build_cache_key(instance_name), payload, STATE_TTL_SECONDS)


def get_instance_state(instance_name: str) -> Optional[InstanceState]:
    """
    Recupera estado da instância do cache.
    """
    if not instance_name:
        return None

    payload = cache.get(_build_cache_key(instance_name))
    if not payload:
        return None

    return InstanceState(
        instance=payload.get("instance", instance_name),
        state=payload.get("state", "unknown"),
        status_reason=payload.get("status_reason"),
        updated_at=payload.get("updated_at", timezone.now().timestamp()),
        raw=payload.get("raw") or {},
    )


def should_defer_instance(instance_name: str) -> Tuple[bool, Optional[InstanceState]]:
    """
    Retorna se devemos adiar chamadas para a instância com base no estado cacheado.
    """
    state = get_instance_state(instance_name)
    if not state:
        return False, None

    if state.is_stale:
        # Estado muito antigo → tratar como disponível
        return False, state

    if state.is_open:
        return False, state

    return True, state


class InstanceTemporarilyUnavailable(Exception):
    """
    Exceção usada quando a instância Evolution não está pronta para receber chamadas
    (ex: state = connecting / close). Inclui payload do estado atual para logs.
    """

    def __init__(self, instance_name: str, state_payload: Optional[dict] = None, wait_seconds: Optional[int] = None):
        self.instance_name = instance_name
        self.state_payload = state_payload or {}
        self.wait_seconds = wait_seconds
        message = (
            f"Instância '{instance_name}' indisponível. "
            f"Estado atual: {self.state_payload}. "
            f"Aguardar ~{wait_seconds}s antes de tentar novamente." if wait_seconds else
            f"Instância '{instance_name}' indisponível. Estado atual: {self.state_payload}."
        )
        super().__init__(message)


def compute_backoff(retry_count: int, base: int = 2, max_seconds: int = MAX_BACKOFF_SECONDS) -> int:
    """
    Calcula tempo (segundos) para aguardar antes de tentar novamente,
    usando backoff exponencial limitado.
    """
    wait = base ** max(0, retry_count)
    return min(wait, max_seconds)

