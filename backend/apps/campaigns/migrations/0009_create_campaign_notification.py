# Generated manually to create CampaignNotification table

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0008_add_tenant_id_to_log'),
        ('contacts', '0001_initial'),
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignNotification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('notification_type', models.CharField(choices=[('response', 'Resposta do Contato'), ('delivery', 'Entrega Confirmada'), ('read', 'Mensagem Lida')], default='response', max_length=20)),
                ('status', models.CharField(choices=[('unread', 'Não Lida'), ('read', 'Lida'), ('replied', 'Respondida')], default='unread', max_length=10)),
                ('received_message', models.TextField(help_text='Mensagem recebida do contato')),
                ('received_timestamp', models.DateTimeField(auto_now_add=True)),
                ('sent_reply', models.TextField(blank=True, help_text='Resposta enviada pelo usuário', null=True)),
                ('sent_timestamp', models.DateTimeField(blank=True, null=True)),
                ('whatsapp_message_id', models.CharField(blank=True, max_length=255, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='campaigns.campaign')),
                ('campaign_contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='campaigns.campaigncontact')),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_notifications', to='contacts.contact')),
                ('instance', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='notifications.whatsappinstance')),
                ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_replies', to='authn.user')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaign_notifications', to='tenancy.tenant')),
            ],
            options={
                'verbose_name': 'Notificação de Campanha',
                'verbose_name_plural': 'Notificações de Campanhas',
                'db_table': 'campaigns_notification',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='campaignnotification',
            index=models.Index(fields=['tenant', '-created_at'], name='campaigns_n_tenant__created_idx'),
        ),
        migrations.AddIndex(
            model_name='campaignnotification',
            index=models.Index(fields=['campaign', 'status'], name='campaigns_n_campaign_status_idx'),
        ),
        migrations.AddIndex(
            model_name='campaignnotification',
            index=models.Index(fields=['contact', '-created_at'], name='campaigns_n_contact_created_idx'),
        ),
        migrations.AddIndex(
            model_name='campaignnotification',
            index=models.Index(fields=['status', '-created_at'], name='campaigns_n_status_created_idx'),
        ),
    ]
