# Generated manually

from django.db import migrations, models, connection
import django.db.models.deletion


def add_tenant_field_if_not_exists(apps, schema_editor):
    """Add tenant field only if it doesn't exist."""
    with connection.cursor() as cursor:
        # Check if tenant_id column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='connections_evolutionconnection' 
            AND column_name='tenant_id'
        """)
        
        if not cursor.fetchone():
            # Column doesn't exist, add it
            cursor.execute("""
                ALTER TABLE connections_evolutionconnection 
                ADD COLUMN tenant_id UUID REFERENCES tenancy_tenant(id) ON DELETE CASCADE
            """)
            
            # Set default tenant for existing records
            cursor.execute("""
                UPDATE connections_evolutionconnection 
                SET tenant_id = (SELECT id FROM tenancy_tenant LIMIT 1)
                WHERE tenant_id IS NULL
            """)
            
            # Make it NOT NULL
            cursor.execute("""
                ALTER TABLE connections_evolutionconnection 
                ALTER COLUMN tenant_id SET NOT NULL
            """)


def remove_tenant_field_if_exists(apps, schema_editor):
    """Remove tenant field if it exists."""
    with connection.cursor() as cursor:
        # Check if tenant_id column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='connections_evolutionconnection' 
            AND column_name='tenant_id'
        """)
        
        if cursor.fetchone():
            # Column exists, remove it
            cursor.execute("""
                ALTER TABLE connections_evolutionconnection 
                DROP COLUMN tenant_id
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
        ('connections', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            add_tenant_field_if_not_exists,
            remove_tenant_field_if_exists,
        ),
    ]
