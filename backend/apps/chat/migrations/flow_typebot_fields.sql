-- Typebot: campos em chat_flow e chat_conversation_flow_state.
-- Pré-requisito: flow_schema.sql (ou migration 0017) já aplicado.
-- Idempotente: adiciona colunas só se não existirem; ALTER COLUMN pode ser executado mais de uma vez.
--
-- Aplicar manualmente (ex.: a partir da pasta backend):
--   psql -U <user> -d <database> -f apps/chat/migrations/flow_typebot_fields.sql
--
-- Se você já tinha aplicado a migration 0018_flow_typebot_fields antes de removê-la,
-- remova o registro para evitar inconsistência:
--   DELETE FROM django_migrations WHERE app = 'chat' AND name = '0018_flow_typebot_fields';

-- 1) chat_flow: Typebot Public ID e URL base da API
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_public_id'
  ) THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_public_id VARCHAR(100) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_base_url'
  ) THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_base_url VARCHAR(200) NOT NULL DEFAULT '';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_flow' AND column_name = 'typebot_prefilled_extra'
  ) THEN
    ALTER TABLE chat_flow ADD COLUMN typebot_prefilled_extra JSONB NOT NULL DEFAULT '{}';
  END IF;
END $$;

-- 2) chat_conversation_flow_state: session ID do Typebot e current_node nullable
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_conversation_flow_state' AND column_name = 'typebot_session_id'
  ) THEN
    ALTER TABLE chat_conversation_flow_state ADD COLUMN typebot_session_id VARCHAR(255) NOT NULL DEFAULT '';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chat_conv_flow_state_typebot_session
  ON chat_conversation_flow_state(typebot_session_id)
  WHERE typebot_session_id <> '';

ALTER TABLE chat_conversation_flow_state ALTER COLUMN current_node_id DROP NOT NULL;
