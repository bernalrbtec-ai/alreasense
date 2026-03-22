# alrea_sense Django Project — Celery app (lazy import so manage.py / migrations work without broker)
from __future__ import annotations

try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:
    celery_app = None  # type: ignore[misc,assignment]
    __all__ = ()

