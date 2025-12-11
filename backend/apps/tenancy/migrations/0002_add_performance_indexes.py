# Generated manually for performance optimization - 2025-12-10
# ✅ IMPROVEMENT: Add missing indexes for Tenant model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Tenant indexes
                CREATE INDEX IF NOT EXISTS idx_tenant_status 
                ON tenancy_tenant(status);
                
                CREATE INDEX IF NOT EXISTS idx_tenant_created_at 
                ON tenancy_tenant(created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_tenant_status_created 
                ON tenancy_tenant(status, created_at DESC);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_tenant_status;
                DROP INDEX IF EXISTS idx_tenant_created_at;
                DROP INDEX IF EXISTS idx_tenant_status_created;
            """
        ),
    ]

