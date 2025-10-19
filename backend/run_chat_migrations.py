"""
Script para aplicar migrations do módulo Chat no Railway
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.core.management import call_command

print("🚀 Aplicando migrations do módulo Chat...")
print("=" * 50)

try:
    # Aplicar migrations do chat
    call_command('migrate', 'chat', verbosity=2)
    print("\n✅ Migrations do Chat aplicadas com sucesso!")
    
    # Verificar tabelas criadas
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'chat_%'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print("\n📋 Tabelas do Chat criadas:")
        for table in tables:
            print(f"   ✓ {table[0]}")
            
except Exception as e:
    print(f"\n❌ Erro ao aplicar migrations: {e}")
    raise

