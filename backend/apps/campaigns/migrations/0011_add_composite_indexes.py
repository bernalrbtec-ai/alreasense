# Generated manually for performance optimization
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('campaigns', '0010_add_performance_indexes'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Composite indexes for common queries
                
                -- Campaign: tenant + status + ordering (para lista de campanhas)
                CREATE INDEX IF NOT EXISTS idx_camp_tenant_status_created 
                ON campaigns_campaign(tenant_id, status, created_at DESC);
                
                -- Campaign: tenant + status (para campanhas ativas)
                CREATE INDEX IF NOT EXISTS idx_camp_tenant_active 
                ON campaigns_campaign(tenant_id, status) 
                WHERE status IN ('active', 'paused', 'scheduled');
                
                -- CampaignContact: campaign + status (para progresso de campanha)
                CREATE INDEX IF NOT EXISTS idx_cc_campaign_status 
                ON campaigns_campaigncontact(campaign_id, status);
                
                -- CampaignContact: campaign + status + retry (para identificar failures)
                CREATE INDEX IF NOT EXISTS idx_cc_campaign_failed 
                ON campaigns_campaigncontact(campaign_id, status, retry_count) 
                WHERE status = 'failed';
                
                -- CampaignLog: campaign + level + created (para monitoring)
                CREATE INDEX IF NOT EXISTS idx_log_campaign_level_time 
                ON campaigns_campaignlog(campaign_id, level, created_at DESC);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_camp_tenant_status_created;
                DROP INDEX IF EXISTS idx_camp_tenant_active;
                DROP INDEX IF EXISTS idx_cc_campaign_status;
                DROP INDEX IF EXISTS idx_cc_campaign_failed;
                DROP INDEX IF EXISTS idx_log_campaign_level_time;
            """
        ),
    ]

