-- Tabela opcional para auditoria de jobs do gateway de teste (BIA) assíncrono.
-- Aplicar manualmente antes do deploy que grava nesta tabela. O fluxo mínimo usa só Redis.
-- Isolamento: cada linha tem tenant_id; listagens/relatórios devem filtrar por tenant.

CREATE TABLE IF NOT EXISTS ai_gateway_test_job (
    job_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    request_id VARCHAR(255) NULL,
    trace_id VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL,
    response_summary TEXT NULL,
    error_message TEXT NULL
);

CREATE INDEX IF NOT EXISTS ai_gateway_test_job_tenant_created_idx
    ON ai_gateway_test_job(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ai_gateway_test_job_status_idx
    ON ai_gateway_test_job(status);

COMMENT ON TABLE ai_gateway_test_job IS 'Auditoria opcional de jobs do gateway de teste BIA (assíncrono); dados por tenant.';
