from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.tenancy.models import Tenant

User = get_user_model()


@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """Send welcome notification when a new user is created."""
    if created and instance.email:
        # TODO: Implementar notificação de boas-vindas com RabbitMQ
        print(f"🎉 Novo usuário criado: {instance.email}")
        # send_welcome_notification.delay(instance.id)  # Removido - Celery deletado


# Note: For plan change, you'll need to update the Tenant model save method
# or create a signal in the tenancy app to detect plan changes

