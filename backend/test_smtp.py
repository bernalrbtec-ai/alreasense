#!/usr/bin/env python
"""
Script para testar envio SMTP localmente
"""
import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from apps.notifications.models import SMTPConfig

def test_smtp():
    """Testar envio SMTP"""
    # Buscar a configuração SMTP
    configs = SMTPConfig.objects.all()
    
    if not configs.exists():
        print("❌ Nenhuma configuração SMTP encontrada")
        return
    
    smtp_config = configs.first()
    
    print("============================================================")
    print("📧 TESTE DE ENVIO SMTP")
    print("============================================================")
    print(f"📌 Config: {smtp_config.name}")
    print(f"📌 Host: {smtp_config.host}:{smtp_config.port}")
    print(f"📌 Username: {smtp_config.username}")
    print(f"📌 Use TLS: {smtp_config.use_tls}")
    print(f"📌 Use SSL: {smtp_config.use_ssl}")
    print(f"📌 From: {smtp_config.from_email}")
    print("============================================================")
    
    test_email = input("Digite o email de destino: ")
    
    print("\n🚀 Enviando email de teste...")
    print("⏱️  Aguarde...\n")
    
    start_time = time.time()
    
    try:
        success, message = smtp_config.test_connection(test_email)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if success:
            print(f"✅ {message}")
            print(f"⏱️  Tempo: {duration:.2f} segundos")
        else:
            print(f"❌ {message}")
            print(f"⏱️  Tempo: {duration:.2f} segundos")
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Erro: {str(e)}")
        print(f"⏱️  Tempo: {duration:.2f} segundos")

if __name__ == '__main__':
    test_smtp()

