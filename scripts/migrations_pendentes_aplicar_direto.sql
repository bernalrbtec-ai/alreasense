-- ============================================================================
-- TODAS AS MIGRAÇÕES PENDENTES EM SQL (aplicar direto no PostgreSQL)
-- Execute este script e registre em django_migrations para o Django não rodar
-- migrate nessas migrações.
-- ============================================================================
-- Inclui: ai.0007, ai.0008, ai.0009, authn.0006, chat.0015
-- Idempotente: pode rodar mais de uma vez (IF NOT EXISTS / DROP IF EXISTS).
-- Sem BEGIN/COMMIT: cada comando usa sua própria transação (evita "transaction aborted").
-- ============================================================================

-- ============================================================================
-- AI 0007: quality/latency/model em ai_transcription_daily_metrics
-- ============================================================================
ALTER TABLE ai_transcription_daily_metrics
  ADD COLUMN IF NOT EXISTS quality_correct_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_transcription_daily_metrics
  ADD COLUMN IF NOT EXISTS quality_incorrect_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_transcription_daily_metrics
  ADD COLUMN IF NOT EXISTS quality_unrated_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_transcription_daily_metrics
  ADD COLUMN IF NOT EXISTS avg_latency_ms NUMERIC(10, 2) NULL;
ALTER TABLE ai_transcription_daily_metrics
  ADD COLUMN IF NOT EXISTS models_used JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ============================================================================
-- AI 0008: Secretária IA (secretary_enabled, TenantSecretaryProfile, índices)
-- ============================================================================
ALTER TABLE ai_tenant_settings
  ADD COLUMN IF NOT EXISTS secretary_enabled BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS ai_tenant_secretary_profile (
  id BIGSERIAL PRIMARY KEY,
  form_data JSONB NOT NULL DEFAULT '{}',
  use_memory BOOLEAN NOT NULL DEFAULT true,
  is_active BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  tenant_id UUID NOT NULL UNIQUE REFERENCES tenancy_tenant(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ai_knowledge_tenant_source
  ON ai_knowledge_document (tenant_id, source);

CREATE INDEX IF NOT EXISTS ai_memory_tenant_conv_created
  ON ai_memory_item (tenant_id, conversation_id, created_at);

-- ============================================================================
-- AUTHN 0006: routing_keywords em Department
-- ============================================================================
ALTER TABLE authn_department
  ADD COLUMN IF NOT EXISTS routing_keywords JSONB NOT NULL DEFAULT '[]';

-- ============================================================================
-- CHAT 0015: campos de qualidade de transcrição em chat_attachment
-- (authn_user.id é BIGINT; se a coluna foi criada como UUID, recria como BIGINT)
-- ============================================================================
ALTER TABLE chat_attachment
  ADD COLUMN IF NOT EXISTS transcription_quality VARCHAR(20) NULL;

ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS check_transcription_quality;
ALTER TABLE chat_attachment ADD CONSTRAINT check_transcription_quality
  CHECK (transcription_quality IN ('correct', 'incorrect') OR transcription_quality IS NULL);

ALTER TABLE chat_attachment
  ADD COLUMN IF NOT EXISTS transcription_quality_feedback_at TIMESTAMP WITH TIME ZONE NULL;

-- FK para authn_user(id): id é BIGINT. Cria coluna só se não existir ou se estiver como UUID.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_attachment'
      AND column_name = 'transcription_quality_feedback_by_id'
  ) THEN
    ALTER TABLE chat_attachment
      ADD COLUMN transcription_quality_feedback_by_id BIGINT NULL
      REFERENCES authn_user(id) ON DELETE SET NULL;
  ELSIF (
    SELECT data_type FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_attachment'
      AND column_name = 'transcription_quality_feedback_by_id'
  ) = 'uuid' THEN
    ALTER TABLE chat_attachment DROP CONSTRAINT IF EXISTS fk_chat_attachment_quality_feedback_by;
    ALTER TABLE chat_attachment DROP COLUMN transcription_quality_feedback_by_id;
    ALTER TABLE chat_attachment
      ADD COLUMN transcription_quality_feedback_by_id BIGINT NULL
      REFERENCES authn_user(id) ON DELETE SET NULL;
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public' AND table_name = 'chat_attachment'
      AND constraint_name = 'fk_chat_attachment_quality_feedback_by'
  ) THEN
    ALTER TABLE chat_attachment
      ADD CONSTRAINT fk_chat_attachment_quality_feedback_by
      FOREIGN KEY (transcription_quality_feedback_by_id) REFERENCES authn_user(id) ON DELETE SET NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chat_attachment_transcription_quality
  ON chat_attachment(transcription_quality)
  WHERE transcription_quality IS NOT NULL;

-- ============================================================================
-- AI 0009: prompt no perfil da secretária e secretary_model nas settings
-- ============================================================================
ALTER TABLE ai_tenant_settings
  ADD COLUMN IF NOT EXISTS secretary_model VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE ai_tenant_secretary_profile
  ADD COLUMN IF NOT EXISTS prompt TEXT NOT NULL DEFAULT '';

-- ============================================================================
-- Registrar todas as migrações como aplicadas (desativa no Django)
-- ============================================================================
INSERT INTO django_migrations (app, name, applied)
SELECT 'ai', '0007_add_quality_latency_model_fields', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'ai' AND name = '0007_add_quality_latency_model_fields');

INSERT INTO django_migrations (app, name, applied)
SELECT 'ai', '0008_secretary_profile_and_indexes', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'ai' AND name = '0008_secretary_profile_and_indexes');

INSERT INTO django_migrations (app, name, applied)
SELECT 'authn', '0006_department_routing_keywords', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'authn' AND name = '0006_department_routing_keywords');

INSERT INTO django_migrations (app, name, applied)
SELECT 'chat', '0015_add_transcription_quality_fields', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'chat' AND name = '0015_add_transcription_quality_fields');

INSERT INTO django_migrations (app, name, applied)
SELECT 'ai', '0009_secretary_prompt_and_model', NOW()
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app = 'ai' AND name = '0009_secretary_prompt_and_model');
