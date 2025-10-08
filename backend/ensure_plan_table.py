#!/usr/bin/env python
"""
Ensure billing_plan table exists.
Creates the table directly if migration doesn't work.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.db import connection
from django.conf import settings


def ensure_plan_table():
    """Create billing_plan table if it doesn't exist."""
    
    # Log database connection info
    db_config = settings.DATABASES['default']
    print(f"\n{'='*60}")
    print('📊 DATABASE CONNECTION INFO')
    print(f"{'='*60}")
    print(f"Engine: {db_config.get('ENGINE', 'N/A')}")
    print(f"Host: {db_config.get('HOST', 'N/A')}")
    print(f"Port: {db_config.get('PORT', 'N/A')}")
    print(f"Database: {db_config.get('NAME', 'N/A')}")
    print(f"User: {db_config.get('USER', 'N/A')}")
    print(f"{'='*60}\n")
    
    # Test connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()[0]
            print(f'✅ Database connected successfully!')
            print(f'   PostgreSQL version: {db_version}\n')
    except Exception as e:
        print(f'❌ Failed to connect to database: {e}\n')
        raise
    
    with connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'billing_plan'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print('✅ Table billing_plan already exists')
            return
        
        print('🔧 Creating billing_plan table...')
        
        # Create the table
        cursor.execute("""
            CREATE TABLE billing_plan (
                id UUID PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                price DECIMAL(10, 2) DEFAULT 0,
                billing_cycle_days INTEGER DEFAULT 30,
                is_free BOOLEAN DEFAULT FALSE,
                max_connections INTEGER DEFAULT 1,
                max_messages_per_month INTEGER DEFAULT 1000,
                features JSONB DEFAULT '[]'::jsonb,
                is_active BOOLEAN DEFAULT TRUE,
                stripe_price_id VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Create index
        cursor.execute("""
            CREATE INDEX idx_billing_plan_is_active ON billing_plan (is_active);
        """)
        
        print('✅ Table billing_plan created successfully')
        
        # Mark migration as applied
        cursor.execute("""
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('billing', '0001_initial', NOW())
            ON CONFLICT DO NOTHING;
        """)
        
        print('✅ Migration marked as applied')


if __name__ == '__main__':
    try:
        ensure_plan_table()
    except Exception as e:
        print(f'❌ Error ensuring plan table: {e}')
        # Don't exit with error - let the app continue
        # sys.exit(1)

