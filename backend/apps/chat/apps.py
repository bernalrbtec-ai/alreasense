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
        import os as _os
        import signal as _signal

        def _graceful_shutdown(signum, frame):
            from apps.chat.webhooks import wait_dify_threads
            wait_dify_threads(timeout=35.0)
            # os._exit(0) evita "Task exception was never retrieved" quando o processo
            # é o start_chat_consumer (asyncio): sys.exit(0) levanta SystemExit no contexto
            # da task bloqueada no Redis e o asyncio loga o erro ao encerrar.
            _os._exit(0)

        # SIGTERM é o sinal enviado pelo gunicorn no graceful reload/shutdown
        try:
            _signal.signal(_signal.SIGTERM, _graceful_shutdown)
        except (OSError, ValueError):
            # Em ambientes onde SIGTERM não pode ser capturado (ex: threads filhas, Windows)
            pass

