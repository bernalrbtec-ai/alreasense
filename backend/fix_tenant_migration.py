#!/usr/bin/env python
"""
Script to fix tenant migration issue.
If tenant_id column already exists, mark the migration as applied.
"""

import os
import sys
import django
from django.db import connection
from django.core.management import execute_from_command_line

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

def check_and_fix_tenant_migration():
    """Check if tenant_id exists and fix migration if needed."""
    
    print("🔍 Checking tenant_id column in connections_evolutionconnection...")
    
    with connection.cursor() as cursor:
        # Check if tenant_id column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='connections_evolutionconnection' 
            AND column_name='tenant_id'
        """)
        
        result = cursor.fetchone()
        
        if result:
            print("✅ tenant_id column already exists!")
            
            # Check if migration is marked as applied
            cursor.execute("""
                SELECT * FROM django_migrations 
                WHERE app='connections' AND name='0002_add_tenant_field'
            """)
            
            migration_exists = cursor.fetchone()
            
            if not migration_exists:
                print("📝 Marking migration as applied...")
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied) 
                    VALUES ('connections', '0002_add_tenant_field', NOW())
                """)
                print("✅ Migration marked as applied!")
            else:
                print("✅ Migration already marked as applied!")
                
        else:
            print("❌ tenant_id column does not exist. Migration will run normally.")
    
    print("🎯 Tenant migration check completed!")

if __name__ == '__main__':
    check_and_fix_tenant_migration()
