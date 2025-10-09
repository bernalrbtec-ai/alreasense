# Migração para remover criptografia e limpar dados corrompidos

from django.db import migrations, models, connection


def clear_corrupted_data(apps, schema_editor):
    """Limpar dados corrompidos e resetar campos"""
    
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
        
        # Limpar senhas SMTP corrompidas
        if smtp_table_exists:
            print("🧹 Limpando senhas SMTP corrompidas...")
            cursor.execute("UPDATE notifications_smtpconfig SET password = '' WHERE password IS NOT NULL")
        
        # Limpar API keys WhatsApp corrompidas
        if whatsapp_table_exists:
            print("🧹 Limpando API keys WhatsApp corrompidas...")
            cursor.execute("UPDATE notifications_whatsappinstance SET api_key = '' WHERE api_key IS NOT NULL")
        
        print("✅ Dados corrompidos limpos com sucesso")


def reverse_clear_data(apps, schema_editor):
    """Não há como reverter a limpeza de dados corrompidos"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_safe_encrypt_fields'),
    ]

    operations = [
        # Limpar dados corrompidos
        migrations.RunPython(
            clear_corrupted_data,
            reverse_clear_data,
        ),
        
        # Reverter campos para CharField normal
        migrations.AlterField(
            model_name='smtpconfig',
            name='password',
            field=models.CharField(max_length=255, help_text='Senha do email'),
        ),
        
        migrations.AlterField(
            model_name='whatsappinstance',
            name='api_key',
            field=models.CharField(max_length=255, help_text='API Key da Evolution API'),
        ),
    ]
