# Generated manually by Paulo Bernal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='conversation_type',
            field=models.CharField(
                choices=[('individual', 'Individual (1:1)'), ('group', 'Grupo do WhatsApp'), ('broadcast', 'Lista de Transmissão')],
                db_index=True,
                default='individual',
                help_text='Individual (1:1), Grupo ou Lista de Transmissão',
                max_length=20,
                verbose_name='Tipo de Conversa'
            ),
        ),
        migrations.AddField(
            model_name='conversation',
            name='group_metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Nome, foto, participantes, etc (apenas para grupos)',
                verbose_name='Metadados do Grupo'
            ),
        ),
        migrations.AddField(
            model_name='message',
            name='sender_name',
            field=models.CharField(
                blank=True,
                help_text='Nome de quem enviou (para grupos WhatsApp)',
                max_length=255,
                verbose_name='Nome do Remetente'
            ),
        ),
        migrations.AddField(
            model_name='message',
            name='sender_phone',
            field=models.CharField(
                blank=True,
                help_text='Telefone de quem enviou (para grupos WhatsApp)',
                max_length=20,
                verbose_name='Telefone do Remetente'
            ),
        ),
    ]

