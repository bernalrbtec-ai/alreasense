import psycopg2

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Conectado ao banco Railway!")
    print("\n" + "="*80)
    
    # Listar todos os usuários
    cursor.execute("""
        SELECT id, email, username, first_name, last_name, is_superuser, is_staff, role, is_active
        FROM authn_user
        ORDER BY id;
    """)
    
    users = cursor.fetchall()
    
    print(f"👥 Total de usuários: {len(users)}\n")
    print("📋 Lista de usuários:")
    print("-" * 80)
    
    for user in users:
        user_id, email, username, first_name, last_name, is_superuser, is_staff, role, is_active = user
        status = "🟢" if is_active else "🔴"
        admin_badge = "👑 SUPERUSER" if is_superuser else f"👤 {role}"
        name = f"{first_name} {last_name}".strip() or "(sem nome)"
        
        print(f"{status} ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Nome: {name}")
        print(f"   Badge: {admin_badge}")
        print("-" * 80)
    
    # Perguntar se quer excluir o admin@alreasense.com
    admin_old_email = "admin@alreasense.com"
    
    cursor.execute("""
        SELECT id FROM authn_user WHERE email = %s;
    """, (admin_old_email,))
    
    old_admin = cursor.fetchone()
    
    if old_admin:
        print(f"\n⚠️  Usuário '{admin_old_email}' encontrado!")
        print(f"🗑️  Excluindo usuário...")
        
        cursor.execute("""
            DELETE FROM authn_user WHERE email = %s;
        """, (admin_old_email,))
        
        conn.commit()
        
        print(f"✅ Usuário '{admin_old_email}' excluído com sucesso!")
    else:
        print(f"\n✅ Usuário '{admin_old_email}' não existe (já foi excluído ou nunca existiu)")
    
    # Listar usuários novamente após exclusão
    cursor.execute("""
        SELECT id, email, first_name, last_name, is_superuser, role
        FROM authn_user
        ORDER BY id;
    """)
    
    remaining_users = cursor.fetchall()
    
    print(f"\n📋 Usuários restantes: {len(remaining_users)}")
    print("-" * 80)
    for user in remaining_users:
        user_id, email, first_name, last_name, is_superuser, role = user
        admin_badge = "👑 SUPERUSER" if is_superuser else f"👤 {role}"
        name = f"{first_name} {last_name}".strip() or "(sem nome)"
        print(f"ID {user_id}: {email} - {name} - {admin_badge}")
    print("-" * 80)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()

