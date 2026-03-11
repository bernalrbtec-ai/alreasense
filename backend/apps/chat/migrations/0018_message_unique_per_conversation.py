# Permite o mesmo message_id da Evolution em conversas diferentes (ex.: duas instâncias
# em tenants diferentes trocando mensagem; cada lado vê a mensagem na sua conversa).

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0017_flow_schema"),
    ]

    operations = [
        # Remover unique global em message_id para permitir mesmo id em conversas diferentes
        migrations.AlterField(
            model_name="message",
            name="message_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="ID único para idempotência",
                max_length=255,
                null=True,
                verbose_name="ID da Evolution",
            ),
        ),
        # Unicidade por (conversation, message_id) quando message_id está preenchido
        migrations.AddConstraint(
            model_name="message",
            constraint=models.UniqueConstraint(
                condition=Q(message_id__isnull=False),
                fields=("conversation", "message_id"),
                name="uniq_chat_message_conversation_message_id",
            ),
        ),
    ]
