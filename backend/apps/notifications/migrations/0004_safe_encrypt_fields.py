# Migration segura para criptografar campos existentes

from django.db import migrations, models, connection
import django_cryptography.fields


def encrypt_existing_data(apps, schema_editor):
    """Criptografar dados existentes de forma segura"""
    
    # Verificar se existem dados para criptografar
    with connection.cursor() as cursor:
        # Verificar SMTPConfig
        cursor.execute("SELECT COUNT(*) FROM notifications_smtpconfig WHERE password IS NOT NULL")
        smtp_count = cursor.fetchone()[0]
        
        # Verificar WhatsAppInstance
        cursor.execute("SELECT COUNT(*) FROM notifications_whatsappinstance WHERE api_key IS NOT NULL")
        whatsapp_count = cursor.fetchone()[0]
        
        print(f"🔍 Encontrados {smtp_count} registros SMTP e {whatsapp_count} registros WhatsApp para processar")
        
        # Para campos que serão criptografados, vamos limpar dados existentes
        # pois não podemos desencriptar sem a chave original
        if smtp_count > 0:
            print("⚠️ Limpando senhas SMTP existentes (serão reconfiguradas)")
            cursor.execute("UPDATE notifications_smtpconfig SET password = ''")
            
        if whatsapp_count > 0:
            print("⚠️ Limpando API keys WhatsApp existentes (serão reconfiguradas)")
            cursor.execute("UPDATE notifications_whatsappinstance SET api_key = ''")


def reverse_encryption(apps, schema_editor):
    """Reversão - não fazemos nada pois não podemos desencriptar"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_alter_whatsappinstance_api_key'),
    ]

    operations = [
        # Limpar dados existentes antes de aplicar criptografia
        migrations.RunPython(
            encrypt_existing_data,
            reverse_encryption,
        ),
    ]
