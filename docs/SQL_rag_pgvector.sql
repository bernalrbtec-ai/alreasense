-- =============================================================================
-- RAG vector store (infra n8n)
-- =============================================================================
-- Tabela de documentos RAG para os workflows rag-upsert e rag-remove (n8n).
-- Resumos aprovados (source=conversation_summary) e perfil empresa (source=company).
-- Aplicar em: PostgreSQL da infra n8n (não no banco do Sense).
-- Idempotente: IF NOT EXISTS em extensão, tabela e índices.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- Documentos RAG: conteúdo + embedding para busca por similaridade
CREATE TABLE IF NOT EXISTS ai_rag_document (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    source VARCHAR(64) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    embedding vector(768),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Unicidade: company = um doc por (tenant_id, source); conversation_summary = um por (tenant_id, source, conversation_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_rag_document_tenant_source_conversation
    ON ai_rag_document (tenant_id, source, COALESCE(metadata->>'conversation_id', ''));

-- Busca por tenant e source (rag-remove: localizar por tenant_id, source, conversation_id)
CREATE INDEX IF NOT EXISTS idx_ai_rag_document_tenant_source
    ON ai_rag_document (tenant_id, source);

-- Índice vetorial para busca por similaridade (cosine)
-- Se a tabela estiver vazia e o ivfflat falhar, crie o índice após inserir dados ou use: USING hnsw (embedding vector_cosine_ops)
CREATE INDEX IF NOT EXISTS idx_ai_rag_document_embedding
    ON ai_rag_document USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

COMMENT ON TABLE ai_rag_document IS 'Documentos RAG (n8n): resumos aprovados e company. Política: source=company replace por (tenant_id, source); source=conversation_summary upsert/remove por (tenant_id, source, metadata.conversation_id).';
COMMENT ON COLUMN ai_rag_document.tenant_id IS 'UUID do tenant (Sense).';
COMMENT ON COLUMN ai_rag_document.source IS 'company | conversation_summary | secretary';
COMMENT ON COLUMN ai_rag_document.embedding IS 'Vetor 768 dimensões (ex.: Qwen).';
COMMENT ON COLUMN ai_rag_document.metadata IS 'Ex.: contact_phone, conversation_id para conversation_summary.';
