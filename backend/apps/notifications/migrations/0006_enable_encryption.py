# Migração para reativar criptografia em campos sensíveis

from django.db import migrations, models
import django_cryptography.fields


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_remove_encryption'),
    ]

    operations = [
        # Reativar criptografia no campo password do SMTPConfig
        migrations.AlterField(
            model_name='smtpconfig',
            name='password',
            field=django_cryptography.fields.encrypt(
                models.CharField(max_length=255, help_text='Senha do email')
            ),
        ),
        
        # Reativar criptografia no campo api_key do WhatsAppInstance
        migrations.AlterField(
            model_name='whatsappinstance',
            name='api_key',
            field=django_cryptography.fields.encrypt(
                models.CharField(max_length=255, help_text='API Key da Evolution API')
            ),
        ),
    ]

