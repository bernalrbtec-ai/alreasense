-- Dify (fase 1): settings + catálogo + binding por escopo + audit log
-- Rodar: psql $DATABASE_URL -f docs/sql/ai/0017_dify_base_tables.up.sql
--
-- Objetivo:
-- - Catalogar apps/agentes Dify manualmente por tenant (sem depender de API de listagem do Dify)
-- - Vincular 1 app por departamento (e opcionalmente inbox via scope_type)
-- - Guardar base_url/enabled por tenant (api_key vem de billing_tenant_product.api_key do produto 'dify')
-- - Registrar audit log de mudanças (sem segredos)
--
-- Requisitos:
-- - PostgreSQL
-- - Extensão pgcrypto (para gen_random_uuid)

SET client_min_messages TO WARNING;

-- UUID helper
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Settings por tenant (sem api_key)
CREATE TABLE IF NOT EXISTS ai_dify_settings (
    tenant_id UUID PRIMARY KEY REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    base_url TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE ai_dify_settings IS 'Config Dify por tenant (enabled/base_url). API key vem de billing_tenant_product.api_key (produto slug=dify).';

-- 2) Catálogo manual (por tenant)
CREATE TABLE IF NOT EXISTS ai_dify_app_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    dify_app_id VARCHAR(128) NOT NULL,
    display_name VARCHAR(200) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unicidade por tenant: um app_id não pode duplicar
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_dify_app_catalog_tenant_app
    ON ai_dify_app_catalog (tenant_id, dify_app_id);

CREATE INDEX IF NOT EXISTS ai_dify_app_catalog_tenant_active_created_idx
    ON ai_dify_app_catalog (tenant_id, is_active, created_at);

COMMENT ON TABLE ai_dify_app_catalog IS 'Catálogo manual de apps/agentes Dify por tenant (soft-delete em is_active).';

-- 3) Binding por escopo (inbox ou department)
CREATE TABLE IF NOT EXISTS ai_dify_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('inbox', 'department')),
    scope_id UUID NULL,
    catalog_id UUID NOT NULL REFERENCES ai_dify_app_catalog(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Um único assignment por tenant para Inbox (scope_id NULL)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_dify_assignment_inbox
    ON ai_dify_assignment (tenant_id)
    WHERE (scope_type = 'inbox' AND scope_id IS NULL);

-- Um único assignment por (tenant, department) para departamentos
CREATE UNIQUE INDEX IF NOT EXISTS uniq_ai_dify_assignment_department
    ON ai_dify_assignment (tenant_id, scope_id)
    WHERE (scope_type = 'department' AND scope_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS ai_dify_assignment_tenant_scope_idx
    ON ai_dify_assignment (tenant_id, scope_type);

CREATE INDEX IF NOT EXISTS ai_dify_assignment_tenant_catalog_idx
    ON ai_dify_assignment (tenant_id, catalog_id);

COMMENT ON TABLE ai_dify_assignment IS 'Vínculo de app Dify do catálogo a Inbox (scope_id NULL) ou departamento (scope_id = authn_department.id).';

-- 4) Audit log (sem segredos)
CREATE TABLE IF NOT EXISTS ai_dify_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    user_id BIGINT NULL REFERENCES authn_user(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    scope_type VARCHAR(20) NULL,
    scope_id UUID NULL,
    catalog_id UUID NULL REFERENCES ai_dify_app_catalog(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_dify_audit_tenant_created_idx
    ON ai_dify_audit_log (tenant_id, created_at);

CREATE INDEX IF NOT EXISTS ai_dify_audit_tenant_action_created_idx
    ON ai_dify_audit_log (tenant_id, action, created_at);

COMMENT ON TABLE ai_dify_audit_log IS 'Audit log Dify (mudanças de settings/catálogo/assignment). Não armazenar api_key.';

