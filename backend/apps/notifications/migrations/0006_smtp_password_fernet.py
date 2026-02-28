# SMTP password: de django-cryptography (signer) para Fernet com CRYPTOGRAPHY_KEY.
# Coluna continua bytea; dados antigos retornam '' ao ler até re-salvar a senha.

from django.db import migrations

from apps.notifications.models import EncryptedPasswordField


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_whatsapptemplate_body'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smtpconfig',
            name='password',
            field=EncryptedPasswordField(help_text='Senha do email'),
        ),
    ]
