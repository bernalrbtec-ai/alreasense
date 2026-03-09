-- Tabela de log de limpeza Redis (Serviços)
-- Rodar este SQL manualmente para criar a tabela. Não usar migration Django.
-- Pré-requisito: tabela authn_user (app authn).
-- Após rodar: o app servicos usa esta tabela via ORM (model RedisCleanupLog).
--
-- Exemplo: psql -U postgres -d seu_banco -f scripts/sql/servicos_redis_cleanup_log.sql

CREATE TABLE IF NOT EXISTS servicos_rediscleanuplog (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed')),
    keys_deleted_profile_pic INTEGER NOT NULL DEFAULT 0,
    keys_deleted_webhook INTEGER NOT NULL DEFAULT 0,
    bytes_freed_estimate BIGINT,
    triggered_by VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (triggered_by IN ('manual', 'scheduled')),
    created_by_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    error_message TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_servicos_rediscleanuplog_status
    ON servicos_rediscleanuplog(status);
CREATE INDEX IF NOT EXISTS idx_servicos_rediscleanuplog_started_at
    ON servicos_rediscleanuplog(started_at DESC);

COMMENT ON TABLE servicos_rediscleanuplog IS 'Log de cada execução de limpeza Redis (cache profile_pic, webhook)';
