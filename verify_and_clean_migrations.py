"""
Verificar e limpar estado das migrations
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO COMPLETA")
    print("=" * 80)
    
    # 1. Verificar duplicatas
    print("\n1️⃣ Verificando duplicatas em django_migrations:")
    cur.execute("""
        SELECT app, name, COUNT(*) as count
        FROM django_migrations
        GROUP BY app, name
        HAVING COUNT(*) > 1;
    """)
    dupes = cur.fetchall()
    if dupes:
        print("   ❌ DUPLICATAS ENCONTRADAS:")
        for d in dupes:
            print(f"      {d[0]}.{d[1]} - {d[2]} vezes")
    else:
        print("   ✅ Sem duplicatas")
    
    # 2. Verificar constraint
    print("\n2️⃣ Verificando UNIQUE constraint:")
    cur.execute("""
        SELECT conname FROM pg_constraint 
        WHERE conname = 'django_migrations_app_name_uniq';
    """)
    constraint = cur.fetchone()
    if constraint:
        print(f"   ✅ Constraint existe: {constraint[0]}")
    else:
        print("   ❌ Constraint NÃO existe")
    
    # 3. Listar migrations de performance
    print("\n3️⃣ Status das migrations de performance:")
    cur.execute("""
        SELECT app, name, applied
        FROM django_migrations
        WHERE name LIKE '%performance%'
        ORDER BY applied;
    """)
    perf_migrations = cur.fetchall()
    if perf_migrations:
        for pm in perf_migrations:
            print(f"   ✅ {pm[0]:<20} | {pm[1]:<40} | {pm[2]}")
    else:
        print("   ℹ️  Nenhuma migration de performance aplicada ainda")
    
    # 4. Contar índices criados
    print("\n4️⃣ Índices de performance criados:")
    cur.execute("""
        SELECT COUNT(*) FROM pg_indexes
        WHERE indexname LIKE 'idx_%' AND schemaname = 'public';
    """)
    idx_count = cur.fetchone()[0]
    print(f"   ✅ Total: {idx_count} índices")
    
    # 5. Mostrar últimas 5 migrations
    print("\n5️⃣ Últimas 5 migrations aplicadas:")
    cur.execute("""
        SELECT app, name, applied
        FROM django_migrations
        ORDER BY applied DESC
        LIMIT 5;
    """)
    recent = cur.fetchall()
    for r in recent:
        print(f"   {r[0]:<20} | {r[1]:<50}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()

