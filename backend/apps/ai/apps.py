import logging
import os
import sys
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _start_secretary_delay_executor() -> None:
    """Inicia em background a thread que processa delays da BIA (Redis)."""
    try:
        from apps.ai.secretary_service import _secretary_delay_executor_loop
        t = threading.Thread(target=_secretary_delay_executor_loop, daemon=True, name="SecretaryDelayRunner")
        t.start()
        logger.info("[AI] Secretary delay executor thread iniciada")
    except Exception as e:
        logger.warning("[AI] Falha ao iniciar secretary delay executor: %s", e)


class AiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai'
    verbose_name = 'AI'

    def ready(self):
        is_migration_script = any(
            x in " ".join(sys.argv)
            for x in ("migrate", "fix_", "create_", "ensure_", "seed_", "check_")
        )
        if is_migration_script:
            return
        if os.environ.get("DISABLE_SECRETARY_DELAY_RUNNER", "0") == "1":
            logger.info("[AI] Secretary delay runner desabilitado por env")
            return
        _start_secretary_delay_executor()
