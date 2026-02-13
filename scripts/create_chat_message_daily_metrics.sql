-- Tabela de métricas diárias de mensagens (chat).
-- Executar manualmente no banco; não usar migrations Django.
-- Compatível com o modelo ChatMessageDailyMetric (ORM).

CREATE TABLE IF NOT EXISTS chat_message_daily_metric (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    department_id UUID NULL REFERENCES authn_department(id) ON DELETE CASCADE,
    total_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    received_count INTEGER NOT NULL DEFAULT 0,
    series_by_hour JSONB NOT NULL DEFAULT '{}',
    avg_first_response_seconds DOUBLE PRECISION NULL,
    by_user JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uniq_chat_message_daily_tenant_date_dept UNIQUE (tenant_id, date, department_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_message_daily_metric_tenant_date
    ON chat_message_daily_metric (tenant_id, date);

COMMENT ON TABLE chat_message_daily_metric IS 'Métricas diárias de mensagens por tenant/departamento para relatórios (pré-agregado por job).';
