-- Tabela TypebotWorkspace: um workspace Typebot por tenant.
-- Aplicar manualmente (ex.: psql ou Railway SQL). Idempotente.

CREATE TABLE IF NOT EXISTS tenancy_typebot_workspace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    workspace_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE tenancy_typebot_workspace IS 'Workspace Typebot associado a um tenant (criado via API admin do Typebot).';
