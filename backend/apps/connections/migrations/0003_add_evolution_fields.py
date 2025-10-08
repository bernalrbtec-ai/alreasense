# Generated manually to fix migration issues

from django.db import migrations, models, connection


def check_column_exists(table_name, column_name):
    """Check if a column exists in the table"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s AND column_name=%s
        """, [table_name, column_name])
        return cursor.fetchone() is not None


def add_columns_if_not_exist(apps, schema_editor):
    """Add columns only if they don't exist"""
    table_name = 'connections_evolutionconnection'
    
    # List of columns to add with their definitions
    columns_to_add = [
        ('base_url', 'ALTER TABLE connections_evolutionconnection ADD COLUMN base_url VARCHAR(200)'),
        ('api_key', 'ALTER TABLE connections_evolutionconnection ADD COLUMN api_key VARCHAR(255)'),
        ('webhook_url', 'ALTER TABLE connections_evolutionconnection ADD COLUMN webhook_url VARCHAR(200)'),
        ('is_active', 'ALTER TABLE connections_evolutionconnection ADD COLUMN is_active BOOLEAN DEFAULT TRUE'),
        ('status', 'ALTER TABLE connections_evolutionconnection ADD COLUMN status VARCHAR(20) DEFAULT \'inactive\''),
        ('last_check', 'ALTER TABLE connections_evolutionconnection ADD COLUMN last_check TIMESTAMP WITH TIME ZONE'),
        ('last_error', 'ALTER TABLE connections_evolutionconnection ADD COLUMN last_error TEXT'),
    ]
    
    with connection.cursor() as cursor:
        for column_name, sql in columns_to_add:
            if not check_column_exists(table_name, column_name):
                cursor.execute(sql)


def remove_columns_if_exist(apps, schema_editor):
    """Remove columns if they exist (for reverse migration)"""
    table_name = 'connections_evolutionconnection'
    columns_to_remove = ['base_url', 'api_key', 'webhook_url', 'is_active', 'status', 'last_check', 'last_error']
    
    with connection.cursor() as cursor:
        for column_name in columns_to_remove:
            if check_column_exists(table_name, column_name):
                cursor.execute(f'ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name}')


class Migration(migrations.Migration):

    dependencies = [
        ('connections', '0002_add_tenant_field'),
    ]

    operations = [
        migrations.RunPython(
            add_columns_if_not_exist,
            remove_columns_if_exist,
        ),
    ]
