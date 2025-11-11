#!/usr/bin/env python
"""
Script para aplicar migration que aumenta tamanho do campo file_url.

PROBLEMA:
- Presigned URLs do S3 ultrapassam 500 caracteres
- Campo file_url era CharField(max_length=500)
- Causava erro: "value too long for type character varying(500)"

SOLUÇÃO:
- Alterar para TextField (sem limite)
- Executar: python apply_file_url_migration.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.management import call_command
from django.db import connection

print("=" * 80)
print("🔧 APLICANDO MIGRATION: file_url TextField")
print("=" * 80)

# 1. Gerar migrations pendentes
print("\n📋 Gerando migrations...")
try:
    call_command('makemigrations', 'chat')
    print("✅ Migrations geradas")
except Exception as e:
    print(f"⚠️  Erro ao gerar migrations: {e}")
    print("   (Pode ser normal se já existem)")

# 2. Aplicar migrations
print("\n🚀 Aplicando migrations...")
try:
    call_command('migrate', 'chat')
    print("✅ Migrations aplicadas")
except Exception as e:
    print(f"❌ Erro ao aplicar migrations: {e}")
    sys.exit(1)

# 3. Verificar campo
print("\n🔍 Verificando campo file_url...")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT 
            column_name, 
            data_type, 
            character_maximum_length
        FROM information_schema.columns 
        WHERE table_name = 'chat_messageattachment' 
        AND column_name = 'file_url';
    """)
    
    result = cursor.fetchone()
    if result:
        col_name, data_type, max_length = result
        print(f"   Column: {col_name}")
        print(f"   Type: {data_type}")
        print(f"   Max Length: {max_length if max_length else 'Unlimited (TextField)'}")
        
        if data_type == 'text':
            print("\n✅ SUCCESS! Campo file_url agora é TextField (sem limite)")
        else:
            print(f"\n⚠️  WARNING: Campo ainda é {data_type} com limite {max_length}")
    else:
        print("❌ Campo file_url não encontrado!")

print("\n" + "=" * 80)
print("✅ MIGRATION COMPLETA!")
print("=" * 80)
print("\n💡 Agora os uploads de áudio com URLs longas devem funcionar!")




























