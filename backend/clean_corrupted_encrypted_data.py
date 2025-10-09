#!/usr/bin/env python
"""
Script para limpar dados criptografados corrompidos em EvolutionConnection.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def clean_corrupted_data():
    """Clean corrupted encrypted data from EvolutionConnection."""
    
    print("=" * 60)
    print("🧹 LIMPANDO DADOS CRIPTOGRAFADOS CORROMPIDOS")
    print("=" * 60)
    
    with connection.cursor() as cursor:
        # DELETAR TODOS os registros para começar limpo
        print("\n1️⃣ Deletando TODOS os registros corrompidos...")
        cursor.execute("""
            DELETE FROM connections_evolutionconnection;
        """)
        rows_deleted = cursor.rowcount
        print(f"   ✅ {rows_deleted} registros deletados")
        
        # Verificar total de registros
        print("\n2️⃣ Verificando registros...")
        cursor.execute("""
            SELECT COUNT(*) FROM connections_evolutionconnection;
        """)
        total = cursor.fetchone()[0]
        print(f"   📊 Total de connections: {total}")
        
        if total > 0:
            cursor.execute("""
                SELECT id, name, base_url, status, is_active
                FROM connections_evolutionconnection
                ORDER BY created_at DESC;
            """)
            
            print("\n   Connections encontradas:")
            print("   " + "-" * 70)
            for row in cursor.fetchall():
                id_val, name, base_url, status, is_active = row
                print(f"   ID: {id_val} | Nome: {name} | URL: {base_url or 'NULL'} | Status: {status} | Ativo: {is_active}")
            print("   " + "-" * 70)
    
    print("\n" + "=" * 60)
    print("✅ LIMPEZA CONCLUÍDA!")
    print("=" * 60)
    print("\nAGORA você pode:")
    print("1. Acessar Admin → Servidor de Instância")
    print("2. Configurar URL e API Key novamente")
    print("3. Os dados serão criptografados corretamente")

if __name__ == '__main__':
    try:
        clean_corrupted_data()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

