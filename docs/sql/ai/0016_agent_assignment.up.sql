-- Associação de agente LibreChat a escopo (Inbox ou departamento). Uma por tenant para Inbox, uma por departamento.
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0016_agent_assignment.up.sql

SET client_min_messages TO WARNING;

CREATE TABLE IF NOT EXISTS ai_agent_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('inbox', 'department')),
    scope_id UUID NULL,
    librechat_agent_id VARCHAR(255) NOT NULL,
    display_name VARCHAR(200) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Um único agente por tenant para Inbox (scope_id NULL)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_agent_assignment_inbox
    ON ai_agent_assignment (tenant_id) WHERE (scope_type = 'inbox' AND scope_id IS NULL);
-- Um único agente por (tenant, department)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_agent_assignment_department
    ON ai_agent_assignment (tenant_id, scope_id) WHERE (scope_type = 'department' AND scope_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS ai_agent_assignment_tenant_scope
    ON ai_agent_assignment (tenant_id, scope_type);

COMMENT ON TABLE ai_agent_assignment IS 'Associação agente LibreChat a Inbox (scope_id NULL) ou departamento (scope_id = authn_department.id).';
