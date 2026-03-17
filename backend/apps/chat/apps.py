"""
Configuração do app Flow Chat.
"""
from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Configuração do módulo de chat."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.chat'
    verbose_name = 'Flow Chat'
    
    def ready(self):
        """Importa signals quando app estiver pronto."""
        import apps.chat.signals  # noqa
        # Registrar handler de graceful shutdown para aguardar threads Dify em andamento
        from django.core.signals import request_finished
        import signal as _signal
        import sys

        def _graceful_shutdown(signum, frame):
            from apps.chat.webhooks import wait_dify_threads
            wait_dify_threads(timeout=35.0)
            sys.exit(0)

        # SIGTERM é o sinal enviado pelo gunicorn no graceful reload/shutdown
        try:
            _signal.signal(_signal.SIGTERM, _graceful_shutdown)
        except (OSError, ValueError):
            # Em ambientes onde SIGTERM não pode ser capturado (ex: threads filhas, Windows)
            pass

