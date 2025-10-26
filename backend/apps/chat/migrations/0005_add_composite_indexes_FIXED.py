# Generated manually for performance optimization
# FIXED VERSION - These indexes already existed, migration just documents them
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0004_add_ai_fields_to_attachment'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Composite indexes (ALREADY EXISTED)
                -- This migration documents what was already in the database
                
                CREATE INDEX IF NOT EXISTS idx_conv_tenant_dept_status_time 
                ON chat_conversation(tenant_id, department_id, status, last_message_at DESC NULLS LAST);
                
                CREATE INDEX IF NOT EXISTS idx_conv_tenant_status_time 
                ON chat_conversation(tenant_id, status, last_message_at DESC NULLS LAST) 
                WHERE status IN ('open', 'pending');
                
                CREATE INDEX IF NOT EXISTS idx_msg_conv_created 
                ON chat_message(conversation_id, created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_msg_conv_status_dir 
                ON chat_message(conversation_id, status, direction) 
                WHERE status = 'delivered' AND direction = 'incoming';
                
                CREATE INDEX IF NOT EXISTS idx_attach_tenant_storage 
                ON chat_attachment(tenant_id, storage_type, expires_at);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_conv_tenant_dept_status_time;
                DROP INDEX IF EXISTS idx_conv_tenant_status_time;
                DROP INDEX IF EXISTS idx_msg_conv_created;
                DROP INDEX IF EXISTS idx_msg_conv_status_dir;
                DROP INDEX IF EXISTS idx_attach_tenant_storage;
            """
        ),
    ]

