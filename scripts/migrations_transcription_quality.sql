-- ============================================================================
-- MIGRAÇÕES: Métricas de Qualidade de Transcrição
-- ============================================================================
-- 
-- Este script contém as migrações para adicionar campos de qualidade,
-- latência e modelos às métricas de transcrição.
--
-- Execute em ordem:
-- 1. Migração 0015 (chat_attachment)
-- 2. Migração 0007 (ai_transcription_daily_metrics)
--
-- ============================================================================

-- ============================================================================
-- MIGRAÇÃO 0015: Adicionar campos de qualidade de transcrição em chat_attachment
-- ============================================================================

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

-- ============================================================================
-- MIGRAÇÃO 0007: Adicionar campos de qualidade, latência e modelos em ai_transcription_daily_metrics
-- ============================================================================

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

-- ============================================================================
-- VERIFICAÇÃO: Verificar se as colunas foram criadas corretamente
-- ============================================================================

-- Verificar colunas em chat_attachment
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'chat_attachment' 
    AND column_name IN (
        'transcription_quality',
        'transcription_quality_feedback_at',
        'transcription_quality_feedback_by_id'
    )
ORDER BY column_name;

-- Verificar colunas em ai_transcription_daily_metrics
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'ai_transcription_daily_metrics' 
    AND column_name IN (
        'quality_correct_count',
        'quality_incorrect_count',
        'quality_unrated_count',
        'avg_latency_ms',
        'models_used'
    )
ORDER BY column_name;

-- ============================================================================
-- FIM DAS MIGRAÇÕES
-- ============================================================================
