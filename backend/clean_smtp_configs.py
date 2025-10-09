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
        # Deletar todos os registros SMTP
        cursor.execute("DELETE FROM notifications_smtpconfig")
        deleted_count = cursor.rowcount
        print(f"🧹 Deletados {deleted_count} registros SMTP")
        
        # Deletar todos os registros WhatsApp
        cursor.execute("DELETE FROM notifications_whatsappinstance")
        deleted_whatsapp = cursor.rowcount
        print(f"🧹 Deletados {deleted_whatsapp} registros WhatsApp")
        
        print("✅ Banco de dados limpo!")
        print("ℹ️  Agora você pode cadastrar novos servidores SMTP com criptografia ativada")

if __name__ == '__main__':
    print("============================================================")
    print("🔧 LIMPANDO CONFIGURAÇÕES SMTP/WHATSAPP")
    print("============================================================")
    clean_smtp_configs()

