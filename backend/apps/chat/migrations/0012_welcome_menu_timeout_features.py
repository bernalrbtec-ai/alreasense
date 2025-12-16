# Generated migration for Welcome Menu Timeout features

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0011_quickreply'),  # Ajustar conforme última migration
    ]

    operations = [
        # 1. Adicionar campos de timeout no WelcomeMenuConfig
        migrations.AddField(
            model_name='welcomemenuconfig',
            name='inactivity_timeout_enabled',
            field=models.BooleanField(
                default=True,
                verbose_name='Timeout de Inatividade',
                help_text='Fecha conversa automaticamente se cliente não responde'
            ),
        ),
        migrations.AddField(
            model_name='welcomemenuconfig',
            name='first_reminder_minutes',
            field=models.IntegerField(
                default=5,
                verbose_name='Primeiro Lembrete (minutos)',
                help_text='Minutos até enviar primeiro lembrete'
            ),
        ),
        migrations.AddField(
            model_name='welcomemenuconfig',
            name='auto_close_minutes',
            field=models.IntegerField(
                default=10,
                verbose_name='Fechamento Automático (minutos)',
                help_text='Minutos até fechar conversa automaticamente'
            ),
        ),
        
        # 2. Criar tabela WelcomeMenuTimeout
        migrations.CreateModel(
            name='WelcomeMenuTimeout',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False
                )),
                ('menu_sent_at', models.DateTimeField(
                    help_text='Quando o menu foi enviado pela última vez',
                    verbose_name='Menu Enviado Em'
                )),
                ('reminder_sent', models.BooleanField(
                    default=False,
                    help_text='Se já enviou o lembrete de 5 minutos',
                    verbose_name='Lembrete Enviado'
                )),
                ('reminder_sent_at', models.DateTimeField(
                    blank=True,
                    help_text='Quando o lembrete foi enviado',
                    null=True,
                    verbose_name='Lembrete Enviado Em'
                )),
                ('is_active', models.BooleanField(
                    db_index=True,
                    default=True,
                    help_text='Se o timeout ainda está ativo (desativa se cliente responder)',
                    verbose_name='Ativo'
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Criado em'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    verbose_name='Atualizado em'
                )),
                ('conversation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='welcome_menu_timeout',
                    to='chat.conversation',
                    verbose_name='Conversa'
                )),
            ],
            options={
                'verbose_name': 'Timeout do Menu de Boas-Vindas',
                'verbose_name_plural': 'Timeouts dos Menus de Boas-Vindas',
                'db_table': 'chat_welcome_menu_timeout',
                'indexes': [
                    models.Index(
                        fields=['is_active', 'menu_sent_at'],
                        name='idx_timeout_active_sent'
                    ),
                    models.Index(
                        fields=['reminder_sent', 'reminder_sent_at'],
                        name='idx_timeout_reminder'
                    ),
                ],
            },
        ),
    ]

