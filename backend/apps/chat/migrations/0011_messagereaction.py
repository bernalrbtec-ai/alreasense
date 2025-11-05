# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0010_alter_messageattachment_media_hash'),
        ('authn', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageReaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('emoji', models.CharField(help_text='Emoji da reação (ex: 👍, ❤️, 😂)', max_length=10, verbose_name='Emoji')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Criado em')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='chat.message', verbose_name='Mensagem')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_reactions', to='authn.user', verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Reação',
                'verbose_name_plural': 'Reações',
                'db_table': 'chat_message_reaction',
                'ordering': ['created_at'],
                'unique_together': {('message', 'user', 'emoji')},
            },
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['message', 'created_at'], name='chat_messa_message_idx'),
        ),
        migrations.AddIndex(
            model_name='messagereaction',
            index=models.Index(fields=['user', 'created_at'], name='chat_messa_user_id_idx'),
        ),
    ]

