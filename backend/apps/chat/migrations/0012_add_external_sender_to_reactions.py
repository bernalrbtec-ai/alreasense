# Generated manually to add external_sender support to MessageReaction

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0011_messagereaction'),
    ]

    operations = [
        # Tornar user nullable
        migrations.AlterField(
            model_name='messagereaction',
            name='user',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='message_reactions',
                to='authn.user',
                verbose_name='Usuário',
                null=True,
                blank=True,
                help_text='NULL para reações de contatos externos (WhatsApp)'
            ),
        ),
        # Adicionar campo external_sender
        migrations.AddField(
            model_name='messagereaction',
            name='external_sender',
            field=models.CharField(
                blank=True,
                max_length=50,
                verbose_name='Remetente Externo',
                help_text='Número do contato que reagiu (para reações recebidas do WhatsApp)'
            ),
        ),
        # Adicionar índice para external_sender
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['external_sender', 'created_at'], name='chat_messa_externa_idx'),
        ),
        # Remover unique_together antigo e adicionar constraints condicionais
        migrations.AlterUniqueTogether(
            name='messagereaction',
            unique_together=set(),
        ),
        # Adicionar constraint para user (quando não é null)
        migrations.AddConstraint(
            model_name='messagereaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(('user__isnull', False)),
                fields=('message', 'user', 'emoji'),
                name='unique_user_reaction_per_message_emoji'
            ),
        ),
        # Adicionar constraint para external_sender (quando não é vazio)
        migrations.AddConstraint(
            model_name='messagereaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(('external_sender__gt', '')),
                fields=('message', 'external_sender', 'emoji'),
                name='unique_external_reaction_per_message_emoji'
            ),
        ),
    ]

