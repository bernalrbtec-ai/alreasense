#!/usr/bin/env python
"""
Script para limpar configurações SMTP corrompidas
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.db import connection

def clean_smtp_configs():
    """Limpar todas as configurações SMTP"""
    with connection.cursor() as cursor:
        # Verificar se a tabela SMTP existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'notifications_smtp_config'
            )
        """)
        smtp_table_exists = cursor.fetchone()[0]
        
        # Verificar se a tabela WhatsApp existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'notifications_whatsapp_instance'
            )
        """)
        whatsapp_table_exists = cursor.fetchone()[0]
        
        if smtp_table_exists:
            # Deletar todos os registros SMTP
            cursor.execute("DELETE FROM notifications_smtp_config")
            deleted_count = cursor.rowcount
            print(f"🧹 Deletados {deleted_count} registros SMTP")
        else:
            print("ℹ️  Tabela SMTP não existe ainda, pulando limpeza")
        
        if whatsapp_table_exists:
            # Deletar todos os registros WhatsApp
            cursor.execute("DELETE FROM notifications_whatsapp_instance")
            deleted_whatsapp = cursor.rowcount
            print(f"🧹 Deletados {deleted_whatsapp} registros WhatsApp")
        else:
            print("ℹ️  Tabela WhatsApp não existe ainda, pulando limpeza")
        
        print("✅ Verificação de limpeza concluída!")
        if smtp_table_exists or whatsapp_table_exists:
            print("ℹ️  Agora você pode cadastrar novos servidores com criptografia ativada")

if __name__ == '__main__':
    print("============================================================")
    print("🔧 LIMPANDO CONFIGURAÇÕES SMTP/WHATSAPP")
    print("============================================================")
    clean_smtp_configs()

