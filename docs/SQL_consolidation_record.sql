-- =============================================================================
-- ConsolidationRecord (um RAG por contato)
-- =============================================================================
-- Tabela: registro de resumos consolidados em uma única memória RAG por contato.
-- Job diário ou manual: um documento consolidado por (tenant, contact_phone).
-- Refresh = UPDATE deste registro + re-upsert no RAG com mesmo consolidated_id.
-- Rodar direto no PostgreSQL (banco do Sense) se não usar migração Django.
-- Idempotente: IF NOT EXISTS.
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_consolidation_record (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    contact_phone VARCHAR(64) NOT NULL DEFAULT '',
    consolidated_id UUID NOT NULL,
    summary_ids JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uniq_ai_consolidation_record_tenant_consolidated
        UNIQUE (tenant_id, consolidated_id),
    CONSTRAINT uniq_ai_consolidation_record_tenant_contact
        UNIQUE (tenant_id, contact_phone)
);

CREATE INDEX IF NOT EXISTS idx_ai_consolidation_record_tenant
    ON ai_consolidation_record (tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_consolidation_record_tenant_contact
    ON ai_consolidation_record (tenant_id, contact_phone);
CREATE INDEX IF NOT EXISTS idx_ai_consolidation_record_created_at
    ON ai_consolidation_record (created_at DESC);

COMMENT ON TABLE ai_consolidation_record IS 'Um RAG por contato. Um registro por (tenant, contact_phone). summary_ids = PKs de ai_conversation_summary. Refresh = UPDATE summary_ids + re-upsert no RAG com mesmo consolidated_id.';

-- Se a tabela já existir sem uniq_tenant_contact, adicionar depois com:
-- ALTER TABLE ai_consolidation_record ADD CONSTRAINT uniq_ai_consolidation_record_tenant_contact UNIQUE (tenant_id, contact_phone);
