from django.apps import AppConfig


class AuthnConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authn'
    verbose_name = 'Authentication'
    
    def ready(self):
        """Importa signals quando o app estiver pronto."""
        import apps.authn.signals