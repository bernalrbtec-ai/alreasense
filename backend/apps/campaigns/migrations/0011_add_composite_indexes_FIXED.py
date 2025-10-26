# Generated manually for performance optimization
# FIXED VERSION - Matches actual database execution
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('campaigns', '0010_add_performance_indexes'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Composite indexes (REAL EXECUTION)
                -- Tabelas corretas: campaigns_contact, campaigns_log
                
                -- CampaignContact (campaigns_contact)
                CREATE INDEX IF NOT EXISTS idx_cc_campaign_status 
                ON campaigns_contact(campaign_id, status);
                
                CREATE INDEX IF NOT EXISTS idx_cc_campaign_failed 
                ON campaigns_contact(campaign_id, status, retry_count) 
                WHERE status = 'failed';
                
                CREATE INDEX IF NOT EXISTS idx_cc_contact_status 
                ON campaigns_contact(contact_id, status);
                
                -- CampaignLog (campaigns_log) - usando log_type e severity
                CREATE INDEX IF NOT EXISTS idx_log_campaign_type_time 
                ON campaigns_log(campaign_id, log_type, created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_log_tenant_severity 
                ON campaigns_log(tenant_id, severity, created_at DESC);
                
                -- CampaignNotification
                CREATE INDEX IF NOT EXISTS idx_notif_tenant_status 
                ON campaigns_notification(tenant_id, status, created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_notif_campaign_status 
                ON campaigns_notification(campaign_id, status);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_cc_campaign_status;
                DROP INDEX IF EXISTS idx_cc_campaign_failed;
                DROP INDEX IF EXISTS idx_cc_contact_status;
                DROP INDEX IF EXISTS idx_log_campaign_type_time;
                DROP INDEX IF EXISTS idx_log_tenant_severity;
                DROP INDEX IF EXISTS idx_notif_tenant_status;
                DROP INDEX IF EXISTS idx_notif_campaign_status;
            """
        ),
    ]

