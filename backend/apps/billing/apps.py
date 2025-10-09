from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.billing'
    verbose_name = 'Billing & Produtos'
    
    def ready(self):
        """Configurações iniciais do app"""
        # Importar signals se necessário
        pass