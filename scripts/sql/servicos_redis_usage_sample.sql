-- Tabela de amostras de uso Redis para gráfico (memória e AOF)
-- Rodar este SQL manualmente OU usar: python manage.py migrate servicos
-- Após rodar: o app servicos grava amostras ao carregar o overview (a cada ~10 min).
--
-- Exemplo: psql -U postgres -d seu_banco -f scripts/sql/servicos_redis_usage_sample.sql

CREATE TABLE IF NOT EXISTS servicos_redisusagesample (
    id BIGSERIAL PRIMARY KEY,
    sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_memory BIGINT NOT NULL,
    aof_current_size BIGINT
);

CREATE INDEX IF NOT EXISTS idx_servicos_redisusagesample_sampled_at
    ON servicos_redisusagesample(sampled_at DESC);

COMMENT ON TABLE servicos_redisusagesample IS 'Amostras de uso Redis (memória e AOF) para gráfico na aba Serviços';