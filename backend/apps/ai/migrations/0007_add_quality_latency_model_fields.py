from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0006_add_gateway_audit'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Adicionar campo quality_correct_count
            ALTER TABLE ai_transcription_daily_metrics 
            ADD COLUMN IF NOT EXISTS quality_correct_count INTEGER NOT NULL DEFAULT 0;

            -- Adicionar campo quality_incorrect_count
            ALTER TABLE ai_transcription_daily_metrics 
            ADD COLUMN IF NOT EXISTS quality_incorrect_count INTEGER NOT NULL DEFAULT 0;

            -- Adicionar campo quality_unrated_count
            ALTER TABLE ai_transcription_daily_metrics 
            ADD COLUMN IF NOT EXISTS quality_unrated_count INTEGER NOT NULL DEFAULT 0;

            -- Adicionar campo avg_latency_ms
            ALTER TABLE ai_transcription_daily_metrics 
            ADD COLUMN IF NOT EXISTS avg_latency_ms NUMERIC(10, 2) NULL;

            -- Adicionar campo models_used (JSONB)
            ALTER TABLE ai_transcription_daily_metrics 
            ADD COLUMN IF NOT EXISTS models_used JSONB NOT NULL DEFAULT '{}'::jsonb;
            """,
            reverse_sql="""
            -- Remover colunas
            ALTER TABLE ai_transcription_daily_metrics DROP COLUMN IF EXISTS models_used;
            ALTER TABLE ai_transcription_daily_metrics DROP COLUMN IF EXISTS avg_latency_ms;
            ALTER TABLE ai_transcription_daily_metrics DROP COLUMN IF EXISTS quality_unrated_count;
            ALTER TABLE ai_transcription_daily_metrics DROP COLUMN IF EXISTS quality_incorrect_count;
            ALTER TABLE ai_transcription_daily_metrics DROP COLUMN IF EXISTS quality_correct_count;
            """
        )
    ]
