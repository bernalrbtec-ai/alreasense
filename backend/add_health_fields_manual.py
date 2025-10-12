#!/usr/bin/env python
"""Adicionar campos de health tracking manualmente"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

print("\n🔧 Adicionando campos de health tracking...")

cursor = connection.cursor()

# Lista de comandos SQL
sql_commands = [
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS health_score INTEGER DEFAULT 100",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS msgs_sent_today INTEGER DEFAULT 0",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS msgs_delivered_today INTEGER DEFAULT 0",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS msgs_read_today INTEGER DEFAULT 0",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS msgs_failed_today INTEGER DEFAULT 0",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS consecutive_errors INTEGER DEFAULT 0",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMP NULL",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS last_health_update TIMESTAMP DEFAULT NOW()",
    "ALTER TABLE notifications_whatsapp_instance ADD COLUMN IF NOT EXISTS health_last_reset DATE NULL",
]

for sql in sql_commands:
    try:
        cursor.execute(sql)
        field_name = sql.split('ADD COLUMN IF NOT EXISTS ')[1].split(' ')[0]
        print(f"✅ {field_name} adicionado")
    except Exception as e:
        print(f"⚠️ {sql[:50]}... - {e}")

print("\n✅ Campos de health tracking adicionados!")




