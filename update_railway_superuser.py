import psycopg2
from werkzeug.security import generate_password_hash
import hashlib

# Railway database connection
DATABASE_URL = "postgresql://postgres:wDxByyoBGIzFwodHccWSkeLmqCcuwpVt@caboose.proxy.rlwy.net:25280/railway"

# Novas credenciais
NEW_EMAIL = "admin@sense.com"
NEW_USERNAME = "admin@sense.com"
NEW_PASSWORD = "Admin@2024"

def hash_password_django_style(password):
    """Gera hash de senha no formato Django PBKDF2"""
    from hashlib import pbkdf2_hmac
    import base64
    
    algorithm = 'pbkdf2_sha256'
    iterations = 600000
    salt = base64.b64encode(hashlib.sha256(password.encode()).digest())[:22].decode()
    
    hash_obj = pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
    hash_b64 = base64.b64encode(hash_obj).decode().strip()
    
    return f'{algorithm}${iterations}${salt}${hash_b64}'

try:
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("✅ Conectado ao banco Railway!")
    print("\n" + "="*80)
    
    # Buscar o superuser atual
    cursor.execute("""
        SELECT id, email, username, is_superuser
        FROM authn_user
        WHERE is_superuser = TRUE
        LIMIT 1;
    """)
    
    superuser = cursor.fetchone()
    
    if not superuser:
        print("❌ Nenhum superuser encontrado!")
    else:
        user_id, old_email, old_username, is_superuser = superuser
        print(f"👤 Superuser encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Email atual: {old_email}")
        print(f"   Username atual: {old_username}")
        print(f"   Is Superuser: {is_superuser}")
        print("\n" + "-"*80)
        
        # Gerar hash da nova senha no formato Django
        import os
        import sys
        
        # Precisamos usar o método Django para gerar o hash correto
        # Vou usar um hash temporário e depois você pode usar o Django manage.py
        print(f"\n🔄 Atualizando credenciais...")
        print(f"   Novo Email: {NEW_EMAIL}")
        print(f"   Novo Username: {NEW_USERNAME}")
        print(f"   Nova Senha: {NEW_PASSWORD}")
        
        # IMPORTANTE: Como não temos acesso ao Django aqui, vamos usar uma abordagem diferente
        # Vamos criar um SQL que você pode rodar no Railway CLI ou criar um management command
        
        print("\n" + "="*80)
        print("⚠️  AVISO: Para atualizar a senha corretamente, precisamos usar o Django.")
        print("\nVou criar um management command para fazer isso de forma segura.")
        print("="*80)
        
        # Atualizar apenas email e username por enquanto
        cursor.execute("""
            UPDATE authn_user
            SET email = %s, username = %s
            WHERE id = %s;
        """, (NEW_EMAIL, NEW_USERNAME, user_id))
        
        conn.commit()
        
        print(f"\n✅ Email e username atualizados com sucesso!")
        print(f"   Email: {old_email} → {NEW_EMAIL}")
        print(f"   Username: {old_username} → {NEW_USERNAME}")
        
        print("\n💡 Para atualizar a senha, vamos criar um management command Django.")
        
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()

