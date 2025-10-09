#!/usr/bin/env python
"""
Script completo para reset e setup do sistema de campanhas
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
sys.path.insert(0, '/app')
django.setup()

from django.core.management import call_command
from django.db import connection

print("🔥 RESET E SETUP COMPLETO DO SISTEMA\n")
print("=" * 60)

# 1. Dropar e recriar schema
print("\n1️⃣ Resetando banco de dados...")
with connection.cursor() as cursor:
    # Drop todas as tabelas
    cursor.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    print("   ✓ Todas as tabelas dropadas")

# 2. Deletar todas as migrations
print("\n2️⃣ Limpando migrations antigas...")
apps_dirs = [
    '/app/apps/authn/migrations',
    '/app/apps/tenancy/migrations',
    '/app/apps/connections/migrations',
    '/app/apps/chat_messages/migrations',
    '/app/apps/ai/migrations',
    '/app/apps/billing/migrations',
    '/app/apps/experiments/migrations',
    '/app/apps/notifications/migrations',
    '/app/apps/contacts/migrations',
    '/app/apps/campaigns/migrations',
]

for app_dir in apps_dirs:
    if os.path.exists(app_dir):
        for file in os.listdir(app_dir):
            if file.endswith('.py') and file != '__init__.py':
                os.remove(os.path.join(app_dir, file))
                print(f"   ✓ Removido {file}")

# 3. Criar migrations do zero
print("\n3️⃣ Criando migrations do zero...")
call_command('makemigrations')

# 4. Aplicar migrations
print("\n4️⃣ Aplicando migrations...")
call_command('migrate')

# 5. Criar superuser
print("\n5️⃣ Criando superuser...")
from apps.authn.models import User
from apps.tenancy.models import Tenant

tenant, _ = Tenant.objects.get_or_create(
    name='ALREA Admin',
    defaults={'slug': 'alrea-admin'}
)
print(f"   ✓ Tenant: {tenant.name}")

user, created = User.objects.get_or_create(
    email='admin@alrea.com',
    defaults={
        'username': 'admin@alrea.com',
        'is_superuser': True,
        'is_staff': True,
        'tenant': tenant
    }
)
if created:
    user.set_password('admin123')
    user.save()
    print(f"   ✓ Superuser criado: admin@alrea.com / admin123")
else:
    print(f"   ℹ️  Superuser já existe")

# 6. Seed de produtos e planos
print("\n6️⃣ Criando produtos e planos...")
call_command('seed_products')

# 7. Seed de campanhas
print("\n7️⃣ Seed de campanhas (feriados)...")
call_command('seed_campaigns')

print("\n" + "=" * 60)
print("✅ SETUP COMPLETO!\n")
print("📋 Credenciais:")
print("   Email: admin@alrea.com")
print("   Senha: admin123")
print("\n🚀 Acesse: http://localhost:5173")
print("=" * 60)

