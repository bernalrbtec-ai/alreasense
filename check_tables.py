"""
Script para verificar tabelas no PostgreSQL do Railway
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def check_tables():
    """Verifica quais tabelas existem no banco"""
    with connection.cursor() as cursor:
        # Listar todas as tabelas
        cursor.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        
        all_tables = cursor.fetchall()
        
        print("\n" + "="*80)
        print("📊 TODAS AS TABELAS NO BANCO")
        print("="*80)
        
        for table in all_tables:
            print(f"  ✓ {table[0]}")
        
        print(f"\n📈 Total: {len(all_tables)} tabelas")
        
        # Procurar por tabelas relevantes
        print("\n" + "="*80)
        print("🔍 TABELAS RELACIONADAS A MENSAGENS, CAMPANHAS E CONTATOS")
        print("="*80)
        
        patterns = ['message', 'campaign', 'contact']
        
        for pattern in patterns:
            print(f"\n🔎 Buscando '{pattern}':")
            found = [t[0] for t in all_tables if pattern.lower() in t[0].lower()]
            
            if found:
                for table in found:
                    print(f"  ✅ {table}")
            else:
                print(f"  ❌ Nenhuma tabela encontrada")
        
        # Verificar índices existentes
        print("\n" + "="*80)
        print("📇 ÍNDICES COMPOSTOS JÁ EXISTENTES")
        print("="*80)
        
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname
            FROM pg_indexes
            WHERE schemaname = 'public' 
              AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname;
        """)
        
        indexes = cursor.fetchall()
        
        if indexes:
            current_table = None
            for schema, table, index in indexes:
                if table != current_table:
                    print(f"\n  📋 {table}:")
                    current_table = table
                print(f"    ✓ {index}")
        else:
            print("  ❌ Nenhum índice composto encontrado")
        
        print("\n" + "="*80)

if __name__ == '__main__':
    check_tables()

