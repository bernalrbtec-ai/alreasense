"""
Script para aplicar correções no banco PostgreSQL da Railway
"""
import psycopg2
import sys

# Railway PostgreSQL connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def main():
    try:
        # Ler o SQL do arquivo
        with open('FIX_MIGRATIONS_RAILWAY_V2.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        print("=" * 80)
        print("🔧 APLICANDO CORREÇÕES NO BANCO DE DADOS RAILWAY")
        print("=" * 80)
        
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True  # Importante para executar comandos DDL
        cur = conn.cursor()
        
        print("\n📝 Executando SQL...")
        print("-" * 80)
        
        # Executar o script SQL
        cur.execute(sql_script)
        
        # Capturar todas as mensagens (NOTICE/RAISE)
        if conn.notices:
            for notice in conn.notices:
                print(notice.strip())
        
        # Buscar resultados (se houver)
        try:
            results = cur.fetchall()
            if results:
                print("\n📊 RESULTADOS:")
                print("-" * 80)
                for row in results:
                    print(f"   {row}")
        except:
            pass  # Sem resultados para buscar
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print("✅ CORREÇÕES APLICADAS COM SUCESSO!")
        print("=" * 80)
        print("\n💡 Próximo passo: Execute 'python backend/manage.py migrate' para reaplicar as migrations")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

