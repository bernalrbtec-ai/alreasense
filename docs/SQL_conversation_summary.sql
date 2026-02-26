-- =============================================================================
-- ConversationSummary (Gestão RAG e Lembranças)
-- =============================================================================
-- Tabela: resumos de conversa para gestão RAG no Sense.
-- Memória (aprovados) fica no pgvector (infra n8n); esta tabela é para gestão.
-- Aplicar em: PostgreSQL (banco do Sense).
-- Idempotente: usar IF NOT EXISTS / IF NOT EXISTS nos índices.
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_conversation_summary (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL,
    contact_phone VARCHAR(64) NOT NULL DEFAULT '',
    contact_name VARCHAR(255) NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_at TIMESTAMP WITH TIME ZONE NULL,
    reviewed_by_id BIGINT NULL REFERENCES authn_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uniq_ai_conversation_summary_tenant_conversation
        UNIQUE (tenant_id, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_conversation_summary_tenant_status
    ON ai_conversation_summary (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_ai_conversation_summary_tenant_contact
    ON ai_conversation_summary (tenant_id, contact_phone);
CREATE INDEX IF NOT EXISTS idx_ai_conversation_summary_conversation_id
    ON ai_conversation_summary (conversation_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversation_summary_created_at
    ON ai_conversation_summary (created_at DESC);

COMMENT ON TABLE ai_conversation_summary IS 'Resumos de conversas para gestão RAG; status pending/approved/rejected. Aprovados são enviados ao pgvector (n8n).';
