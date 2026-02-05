CREATE TABLE IF NOT EXISTS ai_transcription_daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenancy_tenant(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    minutes_total NUMERIC(12, 2) NOT NULL DEFAULT 0,
    audio_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uniq_ai_transcription_daily_tenant_date UNIQUE (tenant_id, date)
);

-- Índice para consultas por tenant + período
CREATE INDEX IF NOT EXISTS idx_ai_transcription_daily_tenant_date
    ON ai_transcription_daily_metrics (tenant_id, date);
