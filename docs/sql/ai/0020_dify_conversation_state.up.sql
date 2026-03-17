-- Dify (fase 2.0): estado de execução por conversa (takeover)
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0020_dify_conversation_state.up.sql
--
-- Objetivo:
-- - Controlar qual agente Dify está ativo por conversa (takeover)
-- - Persistir conversation_id do Dify para manter o histórico entre mensagens
--
-- Requisitos:
-- - Tabela tenancy_tenant
-- - Tabela ai_dify_app_catalog
-- - Tabela chat_conversation
-- - Tabela authn_user

SET client_min_messages TO WARNING;

CREATE TABLE IF NOT EXISTS ai_dify_conversation_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES chat_conversation(id) ON DELETE CASCADE,
    catalog_id UUID NOT NULL REFERENCES ai_dify_app_catalog(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active | stopped
    dify_conversation_id TEXT NULL,
    started_by_user_id BIGINT NULL REFERENCES authn_user(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uma linha por conversa
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_dify_conv_state_conversation
    ON ai_dify_conversation_state (conversation_id);

CREATE INDEX IF NOT EXISTS ai_dify_conv_state_tenant_status_idx
    ON ai_dify_conversation_state (tenant_id, status);

CREATE INDEX IF NOT EXISTS ai_dify_conv_state_tenant_conversation_idx
    ON ai_dify_conversation_state (tenant_id, conversation_id);

COMMENT ON TABLE ai_dify_conversation_state IS 'Estado de takeover de agente Dify por conversa (qual catálogo está ativo + conversation_id do Dify).';

