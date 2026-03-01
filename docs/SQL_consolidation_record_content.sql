-- =============================================================================
-- Coluna content em ai_consolidation_record (cache do texto consolidado para UI)
-- =============================================================================
-- Rodar no PostgreSQL do Sense quando a tabela já existir (ex.: criada por
-- docs/SQL_consolidation_record.sql). Idempotente: IF NOT EXISTS.
-- =============================================================================

ALTER TABLE ai_consolidation_record
ADD COLUMN IF NOT EXISTS content TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN ai_consolidation_record.content IS 'Cache do texto consolidado para exibição na tela de Gestão RAG.';
