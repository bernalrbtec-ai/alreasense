#!/usr/bin/env python
"""
Script para ZERAR completamente as tabelas:
- connections_evolutionconnection
- notifications_whatsapp_instance
- notifications_whatsapp_connection_log

Remove TODOS os dados para começar limpo com criptografia.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def reset_tables():
    """Reset Evolution and WhatsApp tables completely."""
    
    print("=" * 70)
    print("🗑️  ZERANDO TABELAS - EVOLUTION E WHATSAPP")
    print("=" * 70)
    
    with connection.cursor() as cursor:
        # 1. WhatsApp Connection Logs
        print("\n1️⃣ Deletando logs de conexão WhatsApp...")
        try:
            cursor.execute("DELETE FROM notifications_whatsapp_connection_log;")
            count = cursor.rowcount
            print(f"   ✅ {count} logs deletados")
        except Exception as e:
            print(f"   ⚠️  Tabela não existe ou erro: {e}")
        
        # 2. WhatsApp Instances
        print("\n2️⃣ Deletando instâncias WhatsApp...")
        try:
            cursor.execute("DELETE FROM notifications_whatsapp_instance;")
            count = cursor.rowcount
            print(f"   ✅ {count} instâncias deletadas")
        except Exception as e:
            print(f"   ⚠️  Tabela não existe ou erro: {e}")
        
        # 3. Evolution Connections
        print("\n3️⃣ Deletando servidores Evolution...")
        try:
            cursor.execute("DELETE FROM connections_evolutionconnection;")
            count = cursor.rowcount
            print(f"   ✅ {count} servidores deletados")
        except Exception as e:
            print(f"   ⚠️  Tabela não existe ou erro: {e}")
        
        # 4. Verificar se ficou limpo
        print("\n4️⃣ Verificando se tabelas estão vazias...")
        
        tables = [
            ('notifications_whatsapp_connection_log', 'Logs WhatsApp'),
            ('notifications_whatsapp_instance', 'Instâncias WhatsApp'),
            ('connections_evolutionconnection', 'Servidores Evolution'),
        ]
        
        all_clean = True
        for table_name, friendly_name in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                if count == 0:
                    print(f"   ✅ {friendly_name}: 0 registros (LIMPO)")
                else:
                    print(f"   ⚠️  {friendly_name}: {count} registros (NÃO LIMPO)")
                    all_clean = False
            except Exception as e:
                print(f"   ℹ️  {friendly_name}: Tabela não existe")
    
    print("\n" + "=" * 70)
    if all_clean:
        print("✅ TODAS AS TABELAS FORAM ZERADAS COM SUCESSO!")
    else:
        print("⚠️  ALGUMAS TABELAS AINDA TÊM DADOS")
    print("=" * 70)
    print("\n📋 PRÓXIMOS PASSOS:")
    print("1. Reinicie o servidor Django")
    print("2. Acesse: Admin → Servidor de Instância")
    print("3. Configure URL e API Key NOVAMENTE")
    print("4. Dados serão salvos com criptografia correta")
    print("=" * 70)

if __name__ == '__main__':
    try:
        reset_tables()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

