import psycopg2
import os

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Conectado ao banco Railway!")
    print("\n" + "="*80)
    
    # Check if authn_user table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'authn_user'
        );
    """)
    table_exists = cursor.fetchone()[0]
    
    if not table_exists:
        print("❌ Tabela 'authn_user' não existe!")
    else:
        print("✅ Tabela 'authn_user' existe!")
        
        # Count users
        cursor.execute("SELECT COUNT(*) FROM authn_user;")
        user_count = cursor.fetchone()[0]
        print(f"\n👥 Total de usuários: {user_count}")
        
        if user_count > 0:
            # List all users
            cursor.execute("""
                SELECT id, email, username, first_name, last_name, is_superuser, is_active, role
                FROM authn_user
                ORDER BY id;
            """)
            users = cursor.fetchall()
            
            print("\n📋 Usuários cadastrados:")
            print("-" * 80)
            for user in users:
                user_id, email, username, first_name, last_name, is_superuser, is_active, role = user
                status = "🟢 Ativo" if is_active else "🔴 Inativo"
                admin_badge = "👑 SUPERUSER" if is_superuser else f"👤 {role}"
                print(f"ID: {user_id}")
                print(f"  Email: {email}")
                print(f"  Username: {username}")
                print(f"  Nome: {first_name} {last_name}")
                print(f"  Status: {status} | {admin_badge}")
                print("-" * 80)
        else:
            print("\n⚠️ Nenhum usuário encontrado no banco!")
            print("\n💡 Execute o script create_superuser.py para criar o primeiro usuário.")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro ao conectar no banco: {e}")
    import traceback
    traceback.print_exc()

