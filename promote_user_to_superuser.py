import psycopg2

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

# Email do usuário para promover
USER_EMAIL = "paulo.bernal@alrea.ai"

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Conectado ao banco Railway!")
    print("\n" + "="*80)
    
    # Buscar o usuário
    cursor.execute("""
        SELECT id, email, username, first_name, last_name, is_superuser, is_staff, role
        FROM authn_user
        WHERE email = %s;
    """, (USER_EMAIL,))
    
    user = cursor.fetchone()
    
    if not user:
        print(f"❌ Usuário não encontrado: {USER_EMAIL}")
    else:
        user_id, email, username, first_name, last_name, is_superuser, is_staff, role = user
        
        print(f"👤 Usuário encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Nome: {first_name} {last_name}")
        print(f"   Role: {role}")
        print(f"   Is Superuser: {is_superuser}")
        print(f"   Is Staff: {is_staff}")
        print("\n" + "-"*80)
        
        if is_superuser:
            print(f"\n✅ Usuário já é superuser!")
        else:
            print(f"\n🔄 Promovendo usuário a superuser...")
            
            # Atualizar para superuser
            cursor.execute("""
                UPDATE authn_user
                SET is_superuser = TRUE, is_staff = TRUE, role = 'admin'
                WHERE id = %s;
            """, (user_id,))
            
            conn.commit()
            
            print(f"✅ Usuário promovido a superuser com sucesso!")
            print(f"\n📋 Novas permissões:")
            print(f"   Is Superuser: TRUE")
            print(f"   Is Staff: TRUE")
            print(f"   Role: admin")
            print(f"\n🎉 Agora você pode acessar o painel admin completo!")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()

