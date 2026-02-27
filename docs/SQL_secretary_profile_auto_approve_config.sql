-- Adiciona coluna summary_auto_approve_config na tabela do perfil da secretária (aprovação automática RAG).
-- Rodar no banco usado pelo Sense (não no banco do n8n).
-- Idempotente: não falha se a coluna já existir.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'ai_tenant_secretary_profile'
      AND column_name = 'summary_auto_approve_config'
  ) THEN
    ALTER TABLE ai_tenant_secretary_profile
    ADD COLUMN summary_auto_approve_config JSONB NOT NULL DEFAULT '{}';
  END IF;
END $$;
