-- Adiciona coluna duration_seconds à tabela servicos_rediscleanuplog (monitoramento).
-- Rodar após a tabela já existir. Não usar migration Django.

ALTER TABLE servicos_rediscleanuplog
    ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION;

COMMENT ON COLUMN servicos_rediscleanuplog.duration_seconds IS 'Duração da execução em segundos (finished_at - started_at)';
