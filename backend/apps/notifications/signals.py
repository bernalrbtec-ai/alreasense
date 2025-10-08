from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.tenancy.models import Tenant
from .tasks import send_welcome_notification, send_plan_change_notification

User = get_user_model()


@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """Send welcome notification when a new user is created."""
    if created and instance.email:
        # Send welcome notification asynchronously
        send_welcome_notification.delay(instance.id)


# Note: For plan change, you'll need to update the Tenant model save method
# or create a signal in the tenancy app to detect plan changes

