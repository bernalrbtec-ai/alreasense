# Generated migration for adding transcription quality feedback fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0014_add_message_deleted_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Adicionar campo transcription_quality
            ALTER TABLE chat_attachment 
            ADD COLUMN IF NOT EXISTS transcription_quality VARCHAR(20) NULL;
            
            -- Adicionar constraint para transcription_quality
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_transcription_quality;
            ALTER TABLE chat_attachment ADD CONSTRAINT check_transcription_quality 
                CHECK (transcription_quality IN ('correct', 'incorrect') OR transcription_quality IS NULL);
            
            -- Adicionar campo transcription_quality_feedback_at
            ALTER TABLE chat_attachment 
            ADD COLUMN IF NOT EXISTS transcription_quality_feedback_at TIMESTAMP WITH TIME ZONE NULL;
            
            -- Adicionar campo transcription_quality_feedback_by (FK para auth_user)
            ALTER TABLE chat_attachment 
            ADD COLUMN IF NOT EXISTS transcription_quality_feedback_by_id UUID NULL;
            
            -- Adicionar foreign key constraint
            ALTER TABLE chat_attachment 
            ADD CONSTRAINT fk_chat_attachment_quality_feedback_by 
            FOREIGN KEY (transcription_quality_feedback_by_id) 
            REFERENCES auth_user(id) 
            ON DELETE SET NULL;
            
            -- Criar índice para transcription_quality (útil para filtros)
            CREATE INDEX IF NOT EXISTS idx_chat_attachment_transcription_quality 
            ON chat_attachment(transcription_quality) 
            WHERE transcription_quality IS NOT NULL;
            """,
            reverse_sql="""
            -- Remover índice
            DROP INDEX IF EXISTS idx_chat_attachment_transcription_quality;
            
            -- Remover foreign key constraint
            ALTER TABLE chat_attachment 
            DROP CONSTRAINT IF EXISTS fk_chat_attachment_quality_feedback_by;
            
            -- Remover constraint
            ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_transcription_quality;
            
            -- Remover colunas
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS transcription_quality_feedback_by_id;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS transcription_quality_feedback_at;
            ALTER TABLE chat_attachment DROP COLUMN IF EXISTS transcription_quality;
            """
        )
    ]
