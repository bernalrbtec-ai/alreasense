# Migração para remover criptografia e limpar dados corrompidos

from django.db import migrations, models, connection


def clear_corrupted_data(apps, schema_editor):
    """Limpar dados corrompidos e resetar campos"""
    
    with connection.cursor() as cursor:
        # Limpar senhas SMTP corrompidas
        print("🧹 Limpando senhas SMTP corrompidas...")
        cursor.execute("UPDATE notifications_smtpconfig SET password = '' WHERE password IS NOT NULL")
        
        # Limpar API keys WhatsApp corrompidas
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
