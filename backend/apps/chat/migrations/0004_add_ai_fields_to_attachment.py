# Generated manually for AI fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_increase_contact_phone_length'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Adicionar campos para IA no chat_attachment
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS transcription TEXT NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS transcription_language VARCHAR(10) NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS ai_summary TEXT NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS ai_tags JSONB NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS ai_sentiment VARCHAR(20) NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS ai_metadata JSONB NULL;
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) NOT NULL DEFAULT 'pending';
            ALTER TABLE chat_attachment ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE NULL;
            
            -- Criar índice para processing_status
            CREATE INDEX IF NOT EXISTS idx_chat_attachment_processing ON chat_attachment(processing_status);
            
            -- Adicionar constraints para ai_sentiment
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_ai_sentiment;
            ALTER TABLE chat_attachment ADD CONSTRAINT check_ai_sentiment 
                CHECK (ai_sentiment IN ('positive', 'neutral', 'negative') OR ai_sentiment IS NULL);
            
            -- Adicionar constraints para processing_status
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_processing_status;
            ALTER TABLE chat_attachment ADD CONSTRAINT check_processing_status 
                CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped'));
            """,
            reverse_sql="""
            -- Remover campos de IA
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS transcription;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS transcription_language;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS ai_summary;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS ai_tags;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS ai_sentiment;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS ai_metadata;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS processing_status;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS processed_at;
            
            -- Remover índice
            DROP INDEX IF EXISTS idx_chat_attachment_processing;
            
            -- Remover constraints
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_ai_sentiment;
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_processing_status;
            """
        )
    ]

