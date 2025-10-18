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

