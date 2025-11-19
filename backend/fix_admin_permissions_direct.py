#!/usr/bin/env python
"""
Script para corrigir permissões diretamente no banco (mais rápido)
Execute via Railway Dashboard: Shell > python backend/fix_admin_permissions_direct.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection

def fix_admin_permissions_direct():
    print(f"\n{'='*60}")
    print('🔧 CORRIGINDO PERMISSÕES DIRETAMENTE NO BANCO')
    print(f"{'='*60}\n")
    
    ADMIN_EMAIL = 'admin@alreasense.com'
    
    with connection.cursor() as cursor:
        # Verificar estado atual
        print("1️⃣ Verificando estado atual...")
        cursor.execute("""
            SELECT id, email, is_superuser, is_staff, is_active, role
            FROM authn_user
            WHERE email = %s
        """, [ADMIN_EMAIL])
        
        row = cursor.fetchone()
        if not row:
            print(f"❌ Usuário {ADMIN_EMAIL} não encontrado!")
            return
        
        user_id, email, is_superuser, is_staff, is_active, role = row
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   is_superuser: {is_superuser}")
        print(f"   is_staff: {is_staff}")
        print(f"   is_active: {is_active}")
        print(f"   role: {role}")
        
        # Corrigir permissões diretamente no banco
        print(f"\n2️⃣ Corrigindo permissões no banco...")
        cursor.execute("""
            UPDATE authn_user
            SET 
                is_superuser = TRUE,
                is_staff = TRUE,
                is_active = TRUE,
                role = 'admin'
            WHERE email = %s
        """, [ADMIN_EMAIL])
        
        rows_updated = cursor.rowcount
        print(f"   ✅ {rows_updated} linha(s) atualizada(s)")
        
        # Verificar resultado
        print(f"\n3️⃣ Verificando resultado...")
        cursor.execute("""
            SELECT id, email, is_superuser, is_staff, is_active, role
            FROM authn_user
            WHERE email = %s
        """, [ADMIN_EMAIL])
        
        row = cursor.fetchone()
        user_id, email, is_superuser, is_staff, is_active, role = row
        print(f"   ✅ Permissões corrigidas:")
        print(f"      - is_superuser: {is_superuser} ✅")
        print(f"      - is_staff: {is_staff} ✅")
        print(f"      - is_active: {is_active} ✅")
        print(f"      - role: {role} ✅")
    
    print(f"\n{'='*60}")
    print("✅ CORREÇÃO CONCLUÍDA!")
    print(f"{'='*60}")
    print(f"\n🎉 Agora {ADMIN_EMAIL} tem todas as permissões de admin!")

if __name__ == '__main__':
    fix_admin_permissions_direct()

