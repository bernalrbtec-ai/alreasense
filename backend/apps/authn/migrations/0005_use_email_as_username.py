from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0004_add_notification_fields'),
    ]

    operations = [
        # This migration is handled by the model changes
        # The USERNAME_FIELD = 'email' change doesn't require database changes
        # as it's just a Django setting that affects authentication behavior
    ]
