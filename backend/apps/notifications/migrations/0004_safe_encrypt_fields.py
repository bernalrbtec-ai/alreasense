# Migration segura para criptografar campos existentes

from django.db import migrations, models, connection
import django_cryptography.fields


def encrypt_existing_data(apps, schema_editor):
    """Criptografar dados existentes de forma segura"""
    
    # Verificar se as tabelas existem antes de tentar acessá-las
    with connection.cursor() as cursor:
        # Verificar se a tabela notifications_smtpconfig existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'notifications_smtpconfig'
            )
        """)
        smtp_table_exists = cursor.fetchone()[0]
        
        # Verificar se a tabela notifications_whatsappinstance existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'notifications_whatsappinstance'
            )
        """)
        whatsapp_table_exists = cursor.fetchone()[0]
        
        if not smtp_table_exists and not whatsapp_table_exists:
            print("ℹ️ Tabelas ainda não existem, pulando limpeza de dados")
            return
        
        # Se as tabelas existem, verificar e limpar dados
        if smtp_table_exists:
            cursor.execute("SELECT COUNT(*) FROM notifications_smtpconfig WHERE password IS NOT NULL AND password != ''")
            smtp_count = cursor.fetchone()[0]
            
            if smtp_count > 0:
                print(f"⚠️ Limpando {smtp_count} senhas SMTP existentes (serão reconfiguradas)")
                cursor.execute("UPDATE notifications_smtpconfig SET password = ''")
        
        if whatsapp_table_exists:
            cursor.execute("SELECT COUNT(*) FROM notifications_whatsappinstance WHERE api_key IS NOT NULL AND api_key != ''")
            whatsapp_count = cursor.fetchone()[0]
            
            if whatsapp_count > 0:
                print(f"⚠️ Limpando {whatsapp_count} API keys WhatsApp existentes (serão reconfiguradas)")
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
