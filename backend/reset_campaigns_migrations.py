#!/usr/bin/env python
"""Reset campaigns migrations"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()

print("🗑️ Dropando tabelas de campaigns...")
tables = [
    'campaigns_log',
    'campaigns_contact',
    'campaigns_message', 
    'campaigns_campaign_instances',
    'campaigns_campaign_contacts',
    'campaigns_campaign'
]

for table in tables:
    try:
        cursor.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
        print(f"✅ {table} dropada")
    except Exception as e:
        print(f"⚠️ {table}: {e}")

print("\n🗑️ Removendo registro de migrations...")
cursor.execute("DELETE FROM django_migrations WHERE app = 'campaigns'")
print("✅ Migrations removidas")

print("\n✅ Reset completo!")



