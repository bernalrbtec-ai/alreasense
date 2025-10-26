# Generated manually for performance optimization
# FIXED VERSION - Matches actual database execution
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('contacts', '0003_add_performance_indexes'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Composite indexes (REAL EXECUTION)
                -- Tabela correta: contacts_list (não contacts_contactlist)
                -- Sem coluna lifecycle_stage (não existe)
                
                -- Contact (contacts_contact)
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_opted 
                ON contacts_contact(tenant_id, opted_out, is_active) 
                WHERE opted_out = false AND is_active = true;
                
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_state 
                ON contacts_contact(tenant_id, state) 
                WHERE state IS NOT NULL AND is_active = true;
                
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_phone 
                ON contacts_contact(tenant_id, phone);
                
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_active 
                ON contacts_contact(tenant_id, is_active, created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_contact_tenant_source 
                ON contacts_contact(tenant_id, source) 
                WHERE source IS NOT NULL;
                
                -- ContactList (contacts_list)
                CREATE INDEX IF NOT EXISTS idx_list_tenant_active 
                ON contacts_list(tenant_id, is_active);
                
                -- Tag (contacts_tag)
                CREATE INDEX IF NOT EXISTS idx_tag_tenant 
                ON contacts_tag(tenant_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_contact_tenant_opted;
                DROP INDEX IF EXISTS idx_contact_tenant_state;
                DROP INDEX IF EXISTS idx_contact_tenant_phone;
                DROP INDEX IF EXISTS idx_contact_tenant_active;
                DROP INDEX IF EXISTS idx_contact_tenant_source;
                DROP INDEX IF EXISTS idx_list_tenant_active;
                DROP INDEX IF EXISTS idx_tag_tenant;
            """
        ),
    ]

