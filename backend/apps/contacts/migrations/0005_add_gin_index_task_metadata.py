# Generated manually for performance optimization
# ✅ MELHORIA: Adiciona índice GIN para queries JSONB no campo metadata da Task
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('contacts', '0004_add_composite_indexes_FIXED'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="""
                -- ✅ PERFORMANCE: Índice GIN para queries JSONB no campo metadata
                -- Acelera queries como: metadata__is_after_hours_auto, metadata__conversation_id, etc.
                CREATE INDEX IF NOT EXISTS idx_task_metadata_gin 
                ON contacts_task USING GIN (metadata);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_task_metadata_gin;
            """
        ),
    ]

