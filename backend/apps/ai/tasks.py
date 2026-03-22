"""
Tarefas Celery (app `ai`).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="ai.run_dify_incoming_debounce_batch",
    bind=True,
    ignore_result=True,
    acks_late=True,
)
def run_dify_incoming_debounce_batch(self, tenant_id: str, conversation_id: str, wa_instance_id: str, expected_version: int):
    """
    Após countdown, monta batch inbound e chama maybe_handle_dify_takeover uma vez.
    """
    from apps.ai.services.dify_incoming_debounce import execute_debounced_batch

    try:
        execute_debounced_batch(
            tenant_id=str(tenant_id),
            conversation_id=str(conversation_id),
            wa_instance_id=str(wa_instance_id or ""),
            expected_version=int(expected_version),
        )
    except Exception as exc:
        logger.exception(
            "run_dify_incoming_debounce_batch failed tenant=%s conv=%s: %s",
            tenant_id,
            conversation_id,
            exc,
        )
        raise
