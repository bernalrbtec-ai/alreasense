# Generated manually for performance optimization
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('contacts', '0002_contact_state_alter_contact_lifecycle_stage'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Composite indexes for common queries
                
                -- Contact: tenant + lifecycle_stage (para segmentação)
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_lifecycle 
                ON contacts_contact(tenant_id, lifecycle_stage) 
                WHERE is_active = true;
                
                -- Contact: tenant + opted_out (para campanhas)
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_opted 
                ON contacts_contact(tenant_id, opted_out, is_active) 
                WHERE opted_out = false AND is_active = true;
                
                -- Contact: tenant + state (para filtros geográficos)
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_state 
                ON contacts_contact(tenant_id, state) 
                WHERE state IS NOT NULL AND is_active = true;
                
                -- Contact: tenant + phone (para busca rápida)
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_phone 
                ON contacts_contact(tenant_id, phone);
                
                -- ContactList: tenant + active (para listagem)
                CREATE INDEX IF NOT EXISTS idx_list_tenant_active 
                ON contacts_contactlist(tenant_id, is_active);
                
                -- Tag: tenant (para filtros)
                CREATE INDEX IF NOT EXISTS idx_tag_tenant 
                ON contacts_tag(tenant_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_contact_tenant_lifecycle;
                DROP INDEX IF EXISTS idx_contact_tenant_opted;
                DROP INDEX IF EXISTS idx_contact_tenant_state;
                DROP INDEX IF EXISTS idx_contact_tenant_phone;
                DROP INDEX IF EXISTS idx_list_tenant_active;
                DROP INDEX IF EXISTS idx_tag_tenant;
            """
        ),
    ]

