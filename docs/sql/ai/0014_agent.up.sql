-- Tabela ai_agent (plug LibreChat). Equivalente à migration 0014_agent (removida).
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0014_agent.up.sql

-- Tabela
CREATE TABLE IF NOT EXISTS ai_agent (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(100) NOT NULL,
    librechat_agent_id VARCHAR(255) NOT NULL DEFAULT '',
    display_name VARCHAR(200) NOT NULL DEFAULT '',
    system_prompt_override TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tenant_id UUID NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE
);

-- Índice para buscas por slug
CREATE INDEX IF NOT EXISTS ai_agent_slug_idx ON ai_agent (slug);

-- Índice composto slug + tenant (resolução de agente)
CREATE INDEX IF NOT EXISTS ai_agent_slug_tenant_idx ON ai_agent (slug, tenant_id);

-- Unicidade (slug, tenant_id) — um agente por slug por tenant
ALTER TABLE ai_agent
    DROP CONSTRAINT IF EXISTS uniq_ai_agent_slug_tenant;
ALTER TABLE ai_agent
    ADD CONSTRAINT uniq_ai_agent_slug_tenant UNIQUE (slug, tenant_id);

-- Um único agente “sistema” por slug (tenant_id nulo)
DROP INDEX IF EXISTS uniq_ai_agent_slug_system;
CREATE UNIQUE INDEX uniq_ai_agent_slug_system ON ai_agent (slug) WHERE (tenant_id IS NULL);

COMMENT ON TABLE ai_agent IS 'Agentes do plug LibreChat; tenant_id nulo = agente padrão do sistema.';
